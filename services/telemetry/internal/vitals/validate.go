// Package vitals holds the domain rules for biotelemetry samples: what a
// plausible measurement looks like, and what the service refuses to accept.
package vitals

import (
	"errors"
	"fmt"
	"math"
	"time"

	telemetryv1 "maagaparuga/services/telemetry/gen/maagaparuga/telemetry/v1"
)

// Plausibility bounds. These are deliberately wide — the service rejects
// physically impossible or obviously corrupt readings (a sensor reporting
// 500 bpm), it does not make clinical judgements. Narrow clinical
// interpretation is the assessment service's job.
const (
	minHeartRate, maxHeartRate = 20, 300
	minRespRate, maxRespRate   = 3, 80
	minSpO2, maxSpO2           = 50.0, 100.0
	minTempC, maxTempC         = 20.0, 45.0
	minSystolic, maxSystolic   = 40, 300
	minDiastolic, maxDiastolic = 20, 200
	minSkinOhms, maxSkinOhms   = 1.0, 10_000_000.0
	minSkinPH, maxSkinPH       = 3.0, 9.0
	maxClockSkew               = 5 * time.Minute
	maxSampleAge               = 24 * time.Hour
)

// Sentinel errors a sample can fail validation with; callers may match on them.
var (
	ErrNoDeviceID      = errors.New("device_id is required")
	ErrNoRecipient     = errors.New("care_recipient_id is required")
	ErrNoTimestamp     = errors.New("measured_at is required")
	ErrNoMeasurements  = errors.New("sample carries no measurements")
	ErrFutureTimestamp = errors.New("measured_at is too far in the future")
	ErrStaleTimestamp  = errors.New("measured_at is too far in the past")
	ErrNotFinite       = errors.New("measurement is not a finite number")
)

// Validate reports whether a sample may enter the pipeline.
//
// Devices send raw measurements only; there is deliberately no field for a
// device-computed score, so there is nothing to strip here — the contract
// makes the anti-pattern unrepresentable.
func Validate(s *telemetryv1.VitalsSample, now time.Time) error {
	switch {
	case s.GetDeviceId() == "":
		return ErrNoDeviceID
	case s.GetCareRecipientId() == "":
		return ErrNoRecipient
	case s.GetMeasuredAt() == nil:
		return ErrNoTimestamp
	}

	measuredAt := s.GetMeasuredAt().AsTime()
	if measuredAt.After(now.Add(maxClockSkew)) {
		return ErrFutureTimestamp
	}

	if measuredAt.Before(now.Add(-maxSampleAge)) {
		return ErrStaleTimestamp
	}

	measurements := 0

	if v := s.HeartRateBpm; v != nil {
		if *v < minHeartRate || *v > maxHeartRate {
			return rangeErr("heart_rate_bpm", *v, minHeartRate, maxHeartRate)
		}

		measurements++
	}

	if v := s.RespiratoryRate; v != nil {
		if *v < minRespRate || *v > maxRespRate {
			return rangeErr("respiratory_rate", *v, minRespRate, maxRespRate)
		}

		measurements++
	}

	if v := s.Spo2Percent; v != nil {
		if err := checkFloat("spo2_percent", *v, minSpO2, maxSpO2); err != nil {
			return err
		}

		measurements++
	}

	if v := s.BodyTempC; v != nil {
		if err := checkFloat("body_temp_c", *v, minTempC, maxTempC); err != nil {
			return err
		}

		measurements++
	}

	if v := s.BpSystolic; v != nil {
		if *v < minSystolic || *v > maxSystolic {
			return rangeErr("bp_systolic", *v, minSystolic, maxSystolic)
		}

		measurements++
	}

	if v := s.BpDiastolic; v != nil {
		if *v < minDiastolic || *v > maxDiastolic {
			return rangeErr("bp_diastolic", *v, minDiastolic, maxDiastolic)
		}

		measurements++
	}

	if s.BpSystolic != nil && s.BpDiastolic != nil && *s.BpDiastolic >= *s.BpSystolic {
		return fmt.Errorf("bp_diastolic (%d) must be below bp_systolic (%d)",
			*s.BpDiastolic, *s.BpSystolic)
	}

	if v := s.SkinResistanceOhms; v != nil {
		if err := checkFloat("skin_resistance_ohms", *v, minSkinOhms, maxSkinOhms); err != nil {
			return err
		}

		measurements++
	}

	if v := s.SkinPh; v != nil {
		if err := checkFloat("skin_ph", *v, minSkinPH, maxSkinPH); err != nil {
			return err
		}

		measurements++
	}

	if s.GetConsciousness() != telemetryv1.Consciousness_CONSCIOUSNESS_UNSPECIFIED {
		measurements++
	}

	if measurements == 0 {
		return ErrNoMeasurements
	}

	return nil
}

// checkFloat rejects a float measurement that is out of range OR not finite.
//
// The finiteness check is not paranoia: every comparison against NaN is false,
// so a plain `v < lo || v > hi` silently ACCEPTS NaN. A NaN vital would reach
// the time-series store and then the scoring service, where it propagates
// through any arithmetic it touches.
func checkFloat(field string, got, lo, hi float64) error {
	if math.IsNaN(got) || math.IsInf(got, 0) {
		return fmt.Errorf("%s: %w (got %v)", field, ErrNotFinite, got)
	}

	if got < lo || got > hi {
		return rangeErr(field, got, lo, hi)
	}

	return nil
}

func rangeErr[T uint32 | float64](field string, got, lo, hi T) error {
	return fmt.Errorf("%s out of plausible range: got %v, want %v..%v", field, got, lo, hi)
}
