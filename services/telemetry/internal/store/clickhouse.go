// Package store holds the ClickHouse side of the telemetry service: the
// batching writer fed by the broker consumer, and the windowed read query
// used by the web BFF and the assessment service.
package store

import (
	"context"
	"fmt"
	"math"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
	"google.golang.org/protobuf/types/known/timestamppb"

	telemetryv1 "maagaparuga/services/telemetry/gen/maagaparuga/telemetry/v1"
)

const defaultWindowLimit = 500

type Store struct {
	conn driver.Conn
}

// Compile-time proof that Store satisfies the server's read seam.
var _ interface {
	Window(context.Context, string, time.Time, time.Time, uint32) ([]*telemetryv1.VitalsSample, error)
} = (*Store)(nil)

type Config struct {
	Addr     string
	Database string
	Username string
	Password string
}

func Open(ctx context.Context, cfg Config) (*Store, error) {
	conn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{cfg.Addr},
		Auth: clickhouse.Auth{
			Database: cfg.Database,
			Username: cfg.Username,
			Password: cfg.Password,
		},
		DialTimeout: 5 * time.Second,
	})
	if err != nil {
		return nil, fmt.Errorf("open clickhouse: %w", err)
	}

	if err := conn.Ping(ctx); err != nil {
		return nil, fmt.Errorf("ping clickhouse: %w", err)
	}

	return &Store{conn: conn}, nil
}

func (s *Store) Close() error {
	return s.conn.Close()
}

// Migrate creates the vitals table.
//
// ReplacingMergeTree keyed by (care_recipient_id, measured_at, device_id)
// makes at-least-once redelivery from the broker harmless: a replayed sample
// replaces its twin instead of double-counting.
func (s *Store) Migrate(ctx context.Context) error {
	const ddl = `
CREATE TABLE IF NOT EXISTS vitals (
    care_recipient_id    String,
    device_id            String,
    measured_at          DateTime64(3, 'UTC'),
    heart_rate_bpm       Nullable(UInt16),
    respiratory_rate     Nullable(UInt16),
    spo2_percent         Nullable(Float32),
    body_temp_c          Nullable(Float32),
    bp_systolic          Nullable(UInt16),
    bp_diastolic         Nullable(UInt16),
    consciousness        LowCardinality(String),
    skin_resistance_ohms Nullable(Float64),
    skin_ph              Nullable(Float32),
    ingested_at          DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(measured_at)
ORDER BY (care_recipient_id, measured_at, device_id)
TTL toDateTime(measured_at) + INTERVAL 2 YEAR`

	if err := s.conn.Exec(ctx, ddl); err != nil {
		return fmt.Errorf("create vitals table: %w", err)
	}

	return nil
}

// InsertBatch writes a whole batch in one statement — the way ClickHouse
// wants to be fed. Per-sample inserts are the classic ClickHouse anti-pattern.
func (s *Store) InsertBatch(ctx context.Context, samples []*telemetryv1.VitalsSample) error {
	if len(samples) == 0 {
		return nil
	}

	// Columns are named explicitly: an unqualified INSERT expects every
	// column including DEFAULT-valued ones (ingested_at), and an explicit
	// list keeps this code correct when the table gains columns.
	const insert = `INSERT INTO vitals (
		care_recipient_id, device_id, measured_at,
		heart_rate_bpm, respiratory_rate, spo2_percent, body_temp_c,
		bp_systolic, bp_diastolic, consciousness,
		skin_resistance_ohms, skin_ph
	)`

	batch, err := s.conn.PrepareBatch(ctx, insert)
	if err != nil {
		return fmt.Errorf("prepare batch: %w", err)
	}

	for _, sample := range samples {
		err := batch.Append(
			sample.GetCareRecipientId(),
			sample.GetDeviceId(),
			sample.GetMeasuredAt().AsTime(),
			nullableU16(sample.HeartRateBpm),
			nullableU16(sample.RespiratoryRate),
			nullableF32(sample.Spo2Percent),
			nullableF32(sample.BodyTempC),
			nullableU16(sample.BpSystolic),
			nullableU16(sample.BpDiastolic),
			sample.GetConsciousness().String(),
			sample.SkinResistanceOhms,
			nullableF32(sample.SkinPh),
		)
		if err != nil {
			return fmt.Errorf("append row: %w", err)
		}
	}

	if err := batch.Send(); err != nil {
		return fmt.Errorf("send batch: %w", err)
	}

	return nil
}

// Window returns samples for one care recipient in [from, to], newest first.
func (s *Store) Window(
	ctx context.Context,
	careRecipientID string,
	from, to time.Time,
	limit uint32,
) ([]*telemetryv1.VitalsSample, error) {
	if limit == 0 || limit > defaultWindowLimit {
		limit = defaultWindowLimit
	}

	const query = `
SELECT device_id, measured_at, heart_rate_bpm, respiratory_rate, spo2_percent,
       body_temp_c, bp_systolic, bp_diastolic, consciousness,
       skin_resistance_ohms, skin_ph
FROM vitals FINAL
WHERE care_recipient_id = ? AND measured_at BETWEEN ? AND ?
ORDER BY measured_at DESC
LIMIT ?`

	rows, err := s.conn.Query(ctx, query, careRecipientID, from, to, limit)
	if err != nil {
		return nil, fmt.Errorf("query window: %w", err)
	}
	defer rows.Close()

	var samples []*telemetryv1.VitalsSample

	for rows.Next() {
		var (
			deviceID      string
			measuredAt    time.Time
			heartRate     *uint16
			respRate      *uint16
			spo2          *float32
			tempC         *float32
			systolic      *uint16
			diastolic     *uint16
			consciousness string
			skinOhms      *float64
			skinPH        *float32
		)

		if err := rows.Scan(&deviceID, &measuredAt, &heartRate, &respRate, &spo2,
			&tempC, &systolic, &diastolic, &consciousness, &skinOhms, &skinPH); err != nil {
			return nil, fmt.Errorf("scan row: %w", err)
		}

		samples = append(samples, &telemetryv1.VitalsSample{
			DeviceId:           deviceID,
			CareRecipientId:    careRecipientID,
			MeasuredAt:         timestamppb.New(measuredAt),
			HeartRateBpm:       widenU16(heartRate),
			RespiratoryRate:    widenU16(respRate),
			Spo2Percent:        widenF32(spo2),
			BodyTempC:          widenF32(tempC),
			BpSystolic:         widenU16(systolic),
			BpDiastolic:        widenU16(diastolic),
			Consciousness:      telemetryv1.Consciousness(telemetryv1.Consciousness_value[consciousness]),
			SkinResistanceOhms: skinOhms,
			SkinPh:             widenF32(skinPH),
		})
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate rows: %w", err)
	}

	return samples, nil
}

// The proto uses uint32/double; ClickHouse columns are UInt16/Float32.
// These helpers convert without losing the "not measured" distinction.

// nullableU16 narrows a validated measurement. Validation bounds every
// integer vital far below 65535, so this cannot lose data for a sample that
// passed it — but an unchecked conversion would WRAP silently (65536 becomes
// 0, a heart rate of zero), so out-of-range input is clamped and reported
// rather than quietly corrupted.
func nullableU16(v *uint32) *uint16 {
	if v == nil {
		return nil
	}

	value := *v
	if value > math.MaxUint16 {
		value = math.MaxUint16
	}

	narrowed := uint16(value)

	return &narrowed
}

func nullableF32(v *float64) *float32 {
	if v == nil {
		return nil
	}

	narrowed := float32(*v)

	return &narrowed
}

func widenU16(v *uint16) *uint32 {
	if v == nil {
		return nil
	}

	widened := uint32(*v)

	return &widened
}

func widenF32(v *float32) *float64 {
	if v == nil {
		return nil
	}

	widened := float64(*v)

	return &widened
}
