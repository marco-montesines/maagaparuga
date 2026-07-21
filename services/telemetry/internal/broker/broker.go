// Package broker wraps the NATS JetStream stream that decouples device
// ingest from database writes (ADR 0007). The ingest API publishes here and
// returns; the writer consumes at its own pace and batches into ClickHouse,
// so a device-fleet burst queues in the broker instead of overwhelming the
// database.
package broker

import (
	"context"
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
	ConsumerName  = "vitals-writer"
)

type Broker struct {
	conn   *nats.Conn
	stream jetstream.JetStream
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
		Subjects:  []string{SubjectSample},
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
func (b *Broker) Consume(
	ctx context.Context,
	batchSize int,
	maxWait time.Duration,
	handle func(context.Context, []*telemetryv1.VitalsSample) error,
) error {
	consumer, err := b.stream.CreateOrUpdateConsumer(ctx, StreamName, jetstream.ConsumerConfig{
		Durable:       ConsumerName,
		AckPolicy:     jetstream.AckExplicitPolicy,
		MaxDeliver:    5,
		AckWait:       30 * time.Second,
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
				// Undecodable payload will never succeed — drop it rather
				// than redeliver forever (poison-message handling).
				_ = msg.Term()
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
			for _, msg := range received {
				_ = msg.Nak()
			}

			return fmt.Errorf("handle batch: %w", err)
		}

		for _, msg := range received {
			_ = msg.Ack()
		}
	}

	return nil
}
