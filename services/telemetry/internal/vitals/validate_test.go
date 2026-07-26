package vitals_test

import (
	"math"
	"testing"
	"time"

	"google.golang.org/protobuf/types/known/timestamppb"

	telemetryv1 "maagaparuga/services/telemetry/gen/maagaparuga/telemetry/v1"
	"maagaparuga/services/telemetry/internal/vitals"
)

var now = time.Date(2026, 7, 21, 12, 0, 0, 0, time.UTC)

// valid returns a minimal acceptable sample; each test mutates one aspect.
func valid() *telemetryv1.VitalsSample {
	hr := uint32(72)

	return &telemetryv1.VitalsSample{
		DeviceId:        "mock-oximeter-1",
		CareRecipientId: "1",
		MeasuredAt:      timestamppb.New(now.Add(-time.Minute)),
		HeartRateBpm:    &hr,
	}
}

func TestValidate(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name    string
		mutate  func(*telemetryv1.VitalsSample)
		wantErr bool
	}{
		{name: "minimal valid sample", mutate: func(*telemetryv1.VitalsSample) {}},
		{
			name:    "missing device id",
			mutate:  func(s *telemetryv1.VitalsSample) { s.DeviceId = "" },
			wantErr: true,
		},
		{
			name:    "missing care recipient",
			mutate:  func(s *telemetryv1.VitalsSample) { s.CareRecipientId = "" },
			wantErr: true,
		},
		{
			name:    "missing timestamp",
			mutate:  func(s *telemetryv1.VitalsSample) { s.MeasuredAt = nil },
			wantErr: true,
		},
		{
			name:    "no measurements at all",
			mutate:  func(s *telemetryv1.VitalsSample) { s.HeartRateBpm = nil },
			wantErr: true,
		},
		{
			name: "future timestamp beyond clock skew",
			mutate: func(s *telemetryv1.VitalsSample) {
				s.MeasuredAt = timestamppb.New(now.Add(time.Hour))
			},
			wantErr: true,
		},
		{
			name: "small clock skew tolerated",
			mutate: func(s *telemetryv1.VitalsSample) {
				s.MeasuredAt = timestamppb.New(now.Add(time.Minute))
			},
		},
		{
			name: "stale sample",
			mutate: func(s *telemetryv1.VitalsSample) {
				s.MeasuredAt = timestamppb.New(now.Add(-48 * time.Hour))
			},
			wantErr: true,
		},
		{
			name: "implausible heart rate",
			mutate: func(s *telemetryv1.VitalsSample) {
				hr := uint32(500)
				s.HeartRateBpm = &hr
			},
			wantErr: true,
		},
		{
			name: "spo2 above 100 percent",
			mutate: func(s *telemetryv1.VitalsSample) {
				spo2 := 105.0
				s.Spo2Percent = &spo2
			},
			wantErr: true,
		},
		{
			name: "diastolic above systolic",
			mutate: func(s *telemetryv1.VitalsSample) {
				systolic, diastolic := uint32(110), uint32(120)
				s.BpSystolic, s.BpDiastolic = &systolic, &diastolic
			},
			wantErr: true,
		},
		{
			name: "ordered blood pressure pair",
			mutate: func(s *telemetryv1.VitalsSample) {
				systolic, diastolic := uint32(120), uint32(80)
				s.BpSystolic, s.BpDiastolic = &systolic, &diastolic
			},
		},
		{
			// NaN defeats naive range checks: every comparison against NaN is
			// false, so `v < min || v > max` lets it through. A NaN vital would
			// reach the store and then the scoring service.
			name: "NaN heart rate is rejected",
			mutate: func(s *telemetryv1.VitalsSample) {
				spo2 := math.NaN()
				s.Spo2Percent = &spo2
			},
			wantErr: true,
		},
		{
			name: "infinite temperature is rejected",
			mutate: func(s *telemetryv1.VitalsSample) {
				temp := math.Inf(1)
				s.BodyTempC = &temp
			},
			wantErr: true,
		},
		{
			name: "NaN skin pH is rejected",
			mutate: func(s *telemetryv1.VitalsSample) {
				ph := math.NaN()
				s.SkinPh = &ph
			},
			wantErr: true,
		},
		{
			name: "implausible skin resistance is rejected",
			mutate: func(s *telemetryv1.VitalsSample) {
				ohms := -1.0
				s.SkinResistanceOhms = &ohms
			},
			wantErr: true,
		},
		{
			name: "consciousness alone counts as a measurement",
			mutate: func(s *telemetryv1.VitalsSample) {
				s.HeartRateBpm = nil
				s.Consciousness = telemetryv1.Consciousness_CONSCIOUSNESS_VOICE
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()

			sample := valid()
			tt.mutate(sample)

			err := vitals.Validate(sample, now)

			if tt.wantErr && err == nil {
				t.Fatal("expected validation error, got nil")
			}

			if !tt.wantErr && err != nil {
				t.Fatalf("expected sample to be valid, got: %v", err)
			}
		})
	}
}

// The contract has no field for a device-computed score — the predecessor
// system's central flaw is unrepresentable here. This test pins that down: if
// anyone ever adds such a field, it fails.
func TestSampleCarriesNoDeviceComputedScores(t *testing.T) {
	t.Parallel()

	fields := (&telemetryv1.VitalsSample{}).ProtoReflect().Descriptor().Fields()

	for i := range fields.Len() {
		switch name := string(fields.Get(i).Name()); name {
		case "news2_score", "risk_level", "score", "mhrs", "assessment":
			t.Fatalf("vitals contract must not carry device-computed scores, found %q", name)
		}
	}
}
