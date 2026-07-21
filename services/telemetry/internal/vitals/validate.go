// Package vitals holds the domain rules for biotelemetry samples: what a
// plausible measurement looks like, and what the service refuses to accept.
package vitals

import (
	"errors"
	"fmt"
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
	maxClockSkew               = 5 * time.Minute
	maxSampleAge               = 24 * time.Hour
)

var (
	ErrNoDeviceID      = errors.New("device_id is required")
	ErrNoRecipient     = errors.New("care_recipient_id is required")
	ErrNoTimestamp     = errors.New("measured_at is required")
	ErrNoMeasurements  = errors.New("sample carries no measurements")
	ErrFutureTimestamp = errors.New("measured_at is too far in the future")
	ErrStaleTimestamp  = errors.New("measured_at is too far in the past")
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
		if *v < minSpO2 || *v > maxSpO2 {
			return rangeErr("spo2_percent", *v, minSpO2, maxSpO2)
		}
		measurements++
	}
	if v := s.BodyTempC; v != nil {
		if *v < minTempC || *v > maxTempC {
			return rangeErr("body_temp_c", *v, minTempC, maxTempC)
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
	if s.SkinResistanceOhms != nil {
		measurements++
	}
	if s.SkinPh != nil {
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

func rangeErr[T uint32 | float64](field string, got, lo, hi T) error {
	return fmt.Errorf("%s out of plausible range: got %v, want %v..%v", field, got, lo, hi)
}
