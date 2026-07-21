package server_test

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"

	telemetryv1 "maagaparuga/services/telemetry/gen/maagaparuga/telemetry/v1"
	"maagaparuga/services/telemetry/internal/server"
)

type fakePublisher struct {
	published []*telemetryv1.VitalsSample
	err       error
}

func (f *fakePublisher) Publish(_ context.Context, s *telemetryv1.VitalsSample) error {
	if f.err != nil {
		return f.err
	}

	f.published = append(f.published, s)

	return nil
}

type fakeReader struct {
	samples []*telemetryv1.VitalsSample
	gotFrom time.Time
	gotTo   time.Time
}

func (f *fakeReader) Window(
	_ context.Context, _ string, from, to time.Time, _ uint32,
) ([]*telemetryv1.VitalsSample, error) {
	f.gotFrom, f.gotTo = from, to

	return f.samples, nil
}

// fakeStream drives StreamVitals without a network.
type fakeStream struct {
	grpc.ServerStream

	incoming []*telemetryv1.StreamVitalsRequest
	position int
	reply    *telemetryv1.StreamVitalsResponse
}

func (f *fakeStream) Context() context.Context     { return context.Background() }
func (f *fakeStream) SetHeader(metadata.MD) error  { return nil }
func (f *fakeStream) SendHeader(metadata.MD) error { return nil }
func (f *fakeStream) SetTrailer(metadata.MD)       {}

func (f *fakeStream) Recv() (*telemetryv1.StreamVitalsRequest, error) {
	if f.position >= len(f.incoming) {
		return nil, io.EOF
	}

	req := f.incoming[f.position]
	f.position++

	return req, nil
}

func (f *fakeStream) SendAndClose(reply *telemetryv1.StreamVitalsResponse) error {
	f.reply = reply

	return nil
}

func sample(deviceID string, hr uint32) *telemetryv1.StreamVitalsRequest {
	return &telemetryv1.StreamVitalsRequest{
		Sample: &telemetryv1.VitalsSample{
			DeviceId:        deviceID,
			CareRecipientId: "1",
			MeasuredAt:      timestamppb.New(time.Now()),
			HeartRateBpm:    &hr,
		},
	}
}

func newServer(pub server.Publisher, reader server.Reader) *server.Server {
	return server.New(pub, reader, slog.New(slog.DiscardHandler))
}

// A flaky sensor must not disconnect a device: invalid samples are counted and
// skipped while valid ones keep flowing.
func TestStreamVitalsSkipsInvalidSamplesWithoutFailingTheStream(t *testing.T) {
	t.Parallel()

	publisher := &fakePublisher{}
	stream := &fakeStream{incoming: []*telemetryv1.StreamVitalsRequest{
		sample("device-1", 72),
		sample("", 80),           // invalid: no device id
		sample("device-1", 9000), // invalid: implausible heart rate
		sample("device-1", 75),
	}}

	if err := newServer(publisher, &fakeReader{}).StreamVitals(stream); err != nil {
		t.Fatalf("stream returned error: %v", err)
	}

	if got, want := stream.reply.GetAccepted(), uint64(2); got != want {
		t.Errorf("accepted = %d, want %d", got, want)
	}
	if got, want := stream.reply.GetRejected(), uint64(2); got != want {
		t.Errorf("rejected = %d, want %d", got, want)
	}
	if got := len(publisher.published); got != 2 {
		t.Errorf("published %d samples, want 2", got)
	}
}

// The ingest path must never write to the database directly — it publishes and
// returns. If the broker is down, the client learns it can retry.
func TestStreamVitalsReportsUnavailableWhenBrokerFails(t *testing.T) {
	t.Parallel()

	publisher := &fakePublisher{err: errors.New("broker down")}
	stream := &fakeStream{incoming: []*telemetryv1.StreamVitalsRequest{sample("device-1", 72)}}

	err := newServer(publisher, &fakeReader{}).StreamVitals(stream)

	if status.Code(err) != codes.Unavailable {
		t.Fatalf("got %v, want Unavailable", status.Code(err))
	}
}

func TestPublishVitalsRejectsInvalidSample(t *testing.T) {
	t.Parallel()

	publisher := &fakePublisher{}
	req := &telemetryv1.PublishVitalsRequest{
		Sample: &telemetryv1.VitalsSample{DeviceId: "device-1"}, // no recipient/timestamp
	}

	_, err := newServer(publisher, &fakeReader{}).PublishVitals(context.Background(), req)

	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("got %v, want InvalidArgument", status.Code(err))
	}
	if len(publisher.published) != 0 {
		t.Error("invalid sample must not reach the broker")
	}
}

func TestGetWindowRequiresCareRecipient(t *testing.T) {
	t.Parallel()

	_, err := newServer(&fakePublisher{}, &fakeReader{}).
		GetWindow(context.Background(), &telemetryv1.GetWindowRequest{})

	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("got %v, want InvalidArgument", status.Code(err))
	}
}

func TestGetWindowDefaultsToTheLastHour(t *testing.T) {
	t.Parallel()

	reader := &fakeReader{}

	_, err := newServer(&fakePublisher{}, reader).GetWindow(
		context.Background(),
		&telemetryv1.GetWindowRequest{CareRecipientId: "1"},
	)
	if err != nil {
		t.Fatalf("GetWindow: %v", err)
	}

	if span := reader.gotTo.Sub(reader.gotFrom); span != time.Hour {
		t.Errorf("default window = %v, want 1h", span)
	}
}
