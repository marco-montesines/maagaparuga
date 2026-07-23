package server_test

import (
	"context"
	"errors"
	"testing"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"

	"log/slog"
	"time"

	telemetryv1 "maagaparuga/services/telemetry/gen/maagaparuga/telemetry/v1"
	"maagaparuga/services/telemetry/internal/auth"
	"maagaparuga/services/telemetry/internal/authz"
	"maagaparuga/services/telemetry/internal/server"
)

// fakeChecker records calls and returns a scripted result.
type fakeChecker struct {
	allow map[string]bool // key: relation+":"+recipient
	err   error
	calls int
}

func (f *fakeChecker) Check(_ context.Context, _, relation, recipient string) error {
	f.calls++

	if f.err != nil {
		return f.err
	}

	if f.allow[relation+":"+recipient] {
		return nil
	}

	return authz.ErrDenied
}

// authedCtx carries a verified identity, as the auth interceptor would supply.
func authedCtx() context.Context {
	return auth.ContextWithClaims(context.Background(), &auth.Claims{Subject: "device-1"})
}

func serverWithAuthz(pub server.Publisher, reader server.Reader, checker authz.Checker) *server.Server {
	return server.New(pub, reader, checker, slog.New(slog.DiscardHandler))
}

func publishReq(recipient string) *telemetryv1.PublishVitalsRequest {
	hr := uint32(72)

	return &telemetryv1.PublishVitalsRequest{
		Sample: &telemetryv1.VitalsSample{
			DeviceId:        "device-1",
			CareRecipientId: recipient,
			MeasuredAt:      timestamppb.New(time.Now()),
			HeartRateBpm:    &hr,
		},
	}
}

func TestPublishDeniedForUnrelatedRecipient(t *testing.T) {
	t.Parallel()

	pub := &fakePublisher{}
	checker := &fakeChecker{allow: map[string]bool{"vitals_writer:1": true}} // related to 1, not 2

	_, err := serverWithAuthz(pub, &fakeReader{}, checker).
		PublishVitals(authedCtx(), publishReq("2"))

	if status.Code(err) != codes.PermissionDenied {
		t.Fatalf("got %v, want PermissionDenied", status.Code(err))
	}
	if len(pub.published) != 0 {
		t.Error("an unauthorized sample must not reach the broker")
	}
}

func TestPublishAllowedForRelatedRecipient(t *testing.T) {
	t.Parallel()

	pub := &fakePublisher{}
	checker := &fakeChecker{allow: map[string]bool{"vitals_writer:1": true}}

	if _, err := serverWithAuthz(pub, &fakeReader{}, checker).
		PublishVitals(authedCtx(), publishReq("1")); err != nil {
		t.Fatalf("expected allow, got: %v", err)
	}
	if len(pub.published) != 1 {
		t.Error("authorized sample should have been published")
	}
}

// A failing authorization backend must DENY, not fail open.
func TestPublishDeniedWhenAuthzUnavailable(t *testing.T) {
	t.Parallel()

	pub := &fakePublisher{}
	checker := &fakeChecker{err: errors.New("openfga down")}

	_, err := serverWithAuthz(pub, &fakeReader{}, checker).
		PublishVitals(authedCtx(), publishReq("1"))

	if status.Code(err) != codes.PermissionDenied {
		t.Fatalf("got %v, want PermissionDenied", status.Code(err))
	}
	if len(pub.published) != 0 {
		t.Error("must not publish when authorization cannot be established")
	}
}

func TestGetWindowDeniedForUnrelatedRecipient(t *testing.T) {
	t.Parallel()

	checker := &fakeChecker{allow: map[string]bool{"viewer:1": true}}

	_, err := serverWithAuthz(&fakePublisher{}, &fakeReader{}, checker).GetWindow(
		authedCtx(),
		&telemetryv1.GetWindowRequest{CareRecipientId: "2"},
	)

	if status.Code(err) != codes.PermissionDenied {
		t.Fatalf("got %v, want PermissionDenied", status.Code(err))
	}
}

// The stream caches the allow decision per recipient: one call for many
// samples to the same recipient, but a distinct recipient is re-checked.
func TestStreamAuthorizesPerRecipient(t *testing.T) {
	t.Parallel()

	pub := &fakePublisher{}
	checker := &fakeChecker{allow: map[string]bool{"vitals_writer:1": true}}

	stream := &fakeStream{ctx: authedCtx(), incoming: []*telemetryv1.StreamVitalsRequest{
		sample("device-1", 72), // recipient 1 (allowed)
		sample("device-1", 73), // recipient 1 again -> cached, no new call
	}}
	for _, r := range stream.incoming {
		r.Sample.CareRecipientId = "1"
	}

	if err := serverWithAuthz(pub, &fakeReader{}, checker).StreamVitals(stream); err != nil {
		t.Fatalf("stream errored: %v", err)
	}
	if checker.calls != 1 {
		t.Errorf("expected 1 cached authz call for one recipient, got %d", checker.calls)
	}
	if len(pub.published) != 2 {
		t.Errorf("both authorized samples should publish, got %d", len(pub.published))
	}
}

// A stream that tries to write for a recipient the caller may not touch is
// terminated — it cannot be smuggled in among valid samples.
func TestStreamTerminatesOnUnauthorizedRecipient(t *testing.T) {
	t.Parallel()

	pub := &fakePublisher{}
	checker := &fakeChecker{allow: map[string]bool{"vitals_writer:1": true}}

	s1 := sample("device-1", 72)
	s1.Sample.CareRecipientId = "1"
	s2 := sample("device-1", 72)
	s2.Sample.CareRecipientId = "999" // not permitted

	stream := &fakeStream{ctx: authedCtx(), incoming: []*telemetryv1.StreamVitalsRequest{s1, s2}}

	err := serverWithAuthz(pub, &fakeReader{}, checker).StreamVitals(stream)

	if status.Code(err) != codes.PermissionDenied {
		t.Fatalf("got %v, want PermissionDenied", status.Code(err))
	}
	if len(pub.published) != 1 {
		t.Errorf("only the authorized recipient's sample should publish, got %d", len(pub.published))
	}
}
