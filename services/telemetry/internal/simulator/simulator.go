// Package simulator generates mock IoMT device traffic — the replacement for
// the third-party IoT cloud the predecessor systems depended on.
//
// Devices are single-purpose on purpose: a pulse oximeter reports SpO2 and
// heart rate, a thermometer reports temperature. That keeps the "optional
// measurement" semantics of the contract honest and exercises the fleet shape
// the platform claims to support.
package simulator

import (
	"context"
	"fmt"
	"math"
	"math/rand/v2"
	"time"

	"google.golang.org/protobuf/types/known/timestamppb"

	telemetryv1 "maagaparuga/services/telemetry/gen/maagaparuga/telemetry/v1"
)

// Kind is the type of mock IoMT device, which determines the vitals it reports.
type Kind string

// The device kinds a simulated fleet cycles through.
const (
	KindPulseOximeter Kind = "pulse_oximeter"
	KindThermometer   Kind = "thermometer"
	KindBPMonitor     Kind = "bp_monitor"
	KindRespBand      Kind = "respiration_band"
)

// Kinds returns the device kinds a fleet cycles through. It returns a fresh
// slice rather than exposing a package-level variable callers could mutate.
func Kinds() []Kind {
	return []Kind{KindPulseOximeter, KindThermometer, KindBPMonitor, KindRespBand}
}

// Device produces samples for one care recipient. Baselines drift slowly so a
// window of samples looks like a person, not white noise.
type Device struct {
	ID              string
	Kind            Kind
	CareRecipientID string

	rng      *rand.Rand
	baseline map[string]float64
}

// NewDevice creates a device for one care recipient, seeded for deterministic
// output.
func NewDevice(id string, kind Kind, careRecipientID string, seed uint64) *Device {
	return &Device{
		ID:              id,
		Kind:            kind,
		CareRecipientID: careRecipientID,
		rng:             rand.New(rand.NewPCG(seed, seed>>1)),
		baseline: map[string]float64{
			"heart_rate": 72,
			"spo2":       97.5,
			"temp":       36.7,
			"systolic":   118,
			"diastolic":  76,
			"resp_rate":  15,
		},
	}
}

// Sample produces one reading at t. Every value is a raw measurement — the
// simulator never computes a clinical score, mirroring the contract.
func (d *Device) Sample(t time.Time) *telemetryv1.VitalsSample {
	sample := &telemetryv1.VitalsSample{
		DeviceId:        d.ID,
		CareRecipientId: d.CareRecipientID,
		MeasuredAt:      timestamppb.New(t),
	}

	switch d.Kind {
	case KindPulseOximeter:
		hr := uint32(math.Round(d.drift("heart_rate", 0.8, 45, 140)))
		spo2 := d.drift("spo2", 0.15, 88, 100)
		sample.HeartRateBpm = &hr
		sample.Spo2Percent = &spo2

	case KindThermometer:
		temp := math.Round(d.drift("temp", 0.05, 35.2, 39.5)*10) / 10
		sample.BodyTempC = &temp

	case KindBPMonitor:
		systolic := uint32(math.Round(d.drift("systolic", 1.2, 95, 165)))
		diastolic := uint32(math.Round(d.drift("diastolic", 0.9, 55, 105)))
		// Keep the pair physiologically ordered.
		if diastolic >= systolic {
			diastolic = systolic - 30
		}

		sample.BpSystolic = &systolic
		sample.BpDiastolic = &diastolic

	case KindRespBand:
		rr := uint32(math.Round(d.drift("resp_rate", 0.3, 8, 28)))
		sample.RespiratoryRate = &rr
		sample.Consciousness = telemetryv1.Consciousness_CONSCIOUSNESS_ALERT
	}

	return sample
}

// drift is a bounded random walk: the baseline moves a little each sample and
// stays inside plausible limits.
func (d *Device) drift(key string, step, lower, upper float64) float64 {
	value := d.baseline[key] + (d.rng.Float64()*2-1)*step
	value = max(lower, min(upper, value))
	d.baseline[key] = value

	return value
}

// Fleet is a set of devices spread across care recipients.
type Fleet struct {
	Devices []*Device
}

// NewFleet builds a fleet of devices spread across the given care recipients,
// cycling through the device kinds.
func NewFleet(careRecipientIDs []string, devicesPerRecipient int, seed uint64) *Fleet {
	fleet := &Fleet{}

	kinds := Kinds()

	for i, recipientID := range careRecipientIDs {
		for j := range devicesPerRecipient {
			kind := kinds[j%len(kinds)]
			id := fmt.Sprintf("mock-%s-%s-%02d", kind, recipientID, j)
			fleet.Devices = append(fleet.Devices,
				NewDevice(id, kind, recipientID, seed+uint64(i*100+j)))
		}
	}

	return fleet
}

// Run emits one round of samples from every device per interval tick, until
// the context ends or total samples have been produced (total 0 = unbounded).
// The emit callback is what a caller wires to the gRPC stream.
func (f *Fleet) Run(
	ctx context.Context,
	interval time.Duration,
	total int,
	emit func(*telemetryv1.VitalsSample) error,
) error {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	sent := 0

	for {
		select {
		case <-ctx.Done():
			return nil
		case now := <-ticker.C:
			for _, device := range f.Devices {
				if err := emit(device.Sample(now)); err != nil {
					return err
				}

				sent++

				if total > 0 && sent >= total {
					return nil
				}
			}
		}
	}
}
