// Package broker wraps the NATS JetStream stream that decouples device
// ingest from database writes (ADR 0007). The ingest API publishes here and
// returns; the writer consumes at its own pace and batches into ClickHouse,
// so a device-fleet burst queues in the broker instead of overwhelming the
// database.
package broker

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"
	"google.golang.org/protobuf/proto"

	telemetryv1 "maagaparuga/services/telemetry/gen/maagaparuga/telemetry/v1"
)

const (
	StreamName    = "VITALS"
	SubjectSample = "vitals.samples"
	SubjectDead   = "vitals.dead"
	ConsumerName  = "vitals-writer"

	// Redelivery budget. A batch that keeps failing is usually a dependency
	// outage, not a bad message, so the budget is generous and every attempt
	// is spaced out — see Consume for why exhausting it must never be the
	// normal outcome of a database restart.
	maxDeliveries = 100
	nakBackoff    = 5 * time.Second
)

type Broker struct {
	conn   *nats.Conn
	stream jetstream.JetStream

	// Logf reports anomalies (dead-lettered messages, failing batches).
	// Set it at construction; unset means those events go unreported, which
	// is only acceptable in tests.
	Logf func(msg string, args ...any)
}

// Compile-time proof that Broker satisfies the server's publish seam.
var _ interface {
	Publish(context.Context, *telemetryv1.VitalsSample) error
} = (*Broker)(nil)

func Connect(ctx context.Context, url string) (*Broker, error) {
	conn, err := nats.Connect(url,
		nats.MaxReconnects(-1),
		nats.ReconnectWait(time.Second),
	)
	if err != nil {
		return nil, fmt.Errorf("connect nats: %w", err)
	}

	js, err := jetstream.New(conn)
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("jetstream: %w", err)
	}

	b := &Broker{conn: conn, stream: js}

	if err := b.ensureStream(ctx); err != nil {
		conn.Close()
		return nil, err
	}

	return b, nil
}

// ensureStream is idempotent so every replica can call it at startup.
func (b *Broker) ensureStream(ctx context.Context) error {
	_, err := b.stream.CreateOrUpdateStream(ctx, jetstream.StreamConfig{
		Name:      StreamName,
		Subjects:  []string{SubjectSample, SubjectDead},
		Retention: jetstream.WorkQueuePolicy, // acked samples leave the stream
		Storage:   jetstream.FileStorage,
		MaxAge:    7 * 24 * time.Hour, // safety valve if no consumer runs
	})
	if err != nil {
		return fmt.Errorf("ensure stream: %w", err)
	}

	return nil
}

func (b *Broker) Close() {
	b.conn.Close()
}

// Publish hands one validated sample to the broker. The wire format is the
// same protobuf message the device sent — one contract end to end.
func (b *Broker) Publish(ctx context.Context, sample *telemetryv1.VitalsSample) error {
	payload, err := proto.Marshal(sample)
	if err != nil {
		return fmt.Errorf("marshal sample: %w", err)
	}

	if _, err := b.stream.Publish(ctx, SubjectSample, payload); err != nil {
		return fmt.Errorf("publish sample: %w", err)
	}

	return nil
}

// Consume pulls batches of samples and hands each batch to handle. A batch is
// acked only after handle succeeds, so a ClickHouse failure redelivers rather
// than loses data (at-least-once; the ClickHouse table dedupes on replay).
// deadLetter preserves an undecodable message before removing it from the
// work queue, so a serialization bug leaves evidence instead of a silent gap.
func (b *Broker) deadLetter(ctx context.Context, msg jetstream.Msg, cause error) {
	meta, _ := msg.Metadata()

	if _, err := b.stream.Publish(ctx, SubjectDead, msg.Data()); err != nil {
		// Republishing failed too: do NOT terminate, or the payload is gone.
		// Nak instead and let it retry; the alternative is silent loss.
		b.log("dead-letter publish failed, leaving message for redelivery",
			"error", err, "cause", cause)
		_ = msg.NakWithDelay(nakBackoff)

		return
	}

	b.log("undecodable message moved to dead-letter subject",
		"subject", SubjectDead, "cause", cause,
		"stream_sequence", sequenceOf(meta))

	_ = msg.Term()
}

func sequenceOf(meta *jetstream.MsgMetadata) uint64 {
	if meta == nil {
		return 0
	}

	return meta.Sequence.Stream
}

func (b *Broker) onBatchError(_ context.Context, err error) {
	b.log("batch failed, scheduling redelivery", "error", err)
}

// log is a hook so the broker can report anomalies without owning a logger
// type; callers set Logf. Anomalies here are data-loss-adjacent and must
// never be silent.
func (b *Broker) log(msg string, args ...any) {
	if b.Logf == nil {
		return
	}

	b.Logf(msg, args...)
}

func (b *Broker) Consume(
	ctx context.Context,
	batchSize int,
	maxWait time.Duration,
	handle func(context.Context, []*telemetryv1.VitalsSample) error,
) error {
	consumer, err := b.stream.CreateOrUpdateConsumer(ctx, StreamName, jetstream.ConsumerConfig{
		Durable:       ConsumerName,
		AckPolicy:     jetstream.AckExplicitPolicy,
		MaxDeliver:    maxDeliveries,
		AckWait:       2 * time.Minute,
		FilterSubject: SubjectSample,
	})
	if err != nil {
		return fmt.Errorf("ensure consumer: %w", err)
	}

	for ctx.Err() == nil {
		msgs, err := consumer.FetchNoWait(batchSize)
		if err != nil {
			return fmt.Errorf("fetch: %w", err)
		}

		var (
			batch    []*telemetryv1.VitalsSample
			received []jetstream.Msg
		)

		for msg := range msgs.Messages() {
			sample := &telemetryv1.VitalsSample{}
			if err := proto.Unmarshal(msg.Data(), sample); err != nil {
				// Undecodable payload will never succeed on retry. Preserve
				// the bytes on the dead-letter subject before terminating —
				// on a work-queue stream, Term deletes permanently, and
				// silently losing telemetry is the one outcome this pipeline
				// must not have.
				b.deadLetter(ctx, msg, err)

				continue
			}

			batch = append(batch, sample)
			received = append(received, msg)
		}

		if err := msgs.Error(); err != nil {
			return fmt.Errorf("fetch batch: %w", err)
		}

		if len(batch) == 0 {
			select {
			case <-ctx.Done():
				return nil
			case <-time.After(maxWait):
			}

			continue
		}

		if err := handle(ctx, batch); err != nil {
			if errors.Is(err, context.Canceled) {
				// Clean shutdown mid-insert: return the batch for redelivery
				// and stop without a Nak-storm or a nonzero exit.
				for _, msg := range received {
					_ = msg.Nak()
				}

				return nil
			}

			// A failed batch is almost always a downstream outage. Return the
			// messages for redelivery AFTER a delay and keep consuming: an
			// exiting process would crash-loop, and every restart would burn
			// redelivery attempts until the messages were deleted for good.
			for _, msg := range received {
				_ = msg.NakWithDelay(nakBackoff)
			}

			b.onBatchError(ctx, err)

			select {
			case <-ctx.Done():
				return nil
			case <-time.After(nakBackoff):
			}

			continue
		}

		for _, msg := range received {
			_ = msg.Ack()
		}
	}

	return nil
}
