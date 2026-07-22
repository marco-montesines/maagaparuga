// Package server implements the gRPC VitalsService: the device-facing ingest
// path (validate → publish → return) and the windowed read path.
package server

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	telemetryv1 "maagaparuga/services/telemetry/gen/maagaparuga/telemetry/v1"
	"maagaparuga/services/telemetry/internal/auth"
	"maagaparuga/services/telemetry/internal/authz"
	"maagaparuga/services/telemetry/internal/vitals"
)

const defaultWindow = time.Hour

// Publisher is the broker seam — the server never touches the database on the
// ingest path (ADR 0007).
type Publisher interface {
	Publish(ctx context.Context, sample *telemetryv1.VitalsSample) error
}

// Reader is the query seam for windowed reads.
type Reader interface {
	Window(ctx context.Context, careRecipientID string, from, to time.Time, limit uint32) ([]*telemetryv1.VitalsSample, error)
}

// Verify at compile time that Server satisfies the generated service
// interface, rather than discovering a mismatch at registration.
var _ telemetryv1.VitalsServiceServer = (*Server)(nil)

type Server struct {
	telemetryv1.UnimplementedVitalsServiceServer

	publisher Publisher
	reader    Reader
	authz     authz.Checker // nil = authorization not enforced (dev only)
	log       *slog.Logger
	now       func() time.Time
}

// New builds a server. A nil authz.Checker disables per-object authorization
// — acceptable ONLY when authentication is also disabled for local
// development; in that mode there is no caller identity to authorize against.
func New(publisher Publisher, reader Reader, checker authz.Checker, log *slog.Logger) *Server {
	return &Server{
		publisher: publisher,
		reader:    reader,
		authz:     checker,
		log:       log,
		now:       time.Now,
	}
}

// authorize checks that the authenticated caller holds `relation` on the care
// recipient. When no checker is configured (dev, auth disabled) it allows —
// but that path is unreachable in any mode that has a caller identity, because
// the checker is wired whenever authentication is.
func (s *Server) authorize(ctx context.Context, relation, careRecipientID string) error {
	if s.authz == nil {
		return nil
	}

	claims, ok := auth.ClaimsFrom(ctx)
	if !ok {
		// Authorization is enforced but there is no verified identity — deny.
		return status.Error(codes.Unauthenticated, "no verified identity")
	}

	switch err := s.authz.Check(ctx, claims.Subject, relation, careRecipientID); {
	case err == nil:
		return nil
	case errors.Is(err, authz.ErrDenied):
		return status.Error(codes.PermissionDenied, "not permitted for this care recipient")
	default:
		// A transport/config failure must NOT fail open: deny, and log the
		// real cause for operators.
		s.log.ErrorContext(ctx, "authorization check failed", "error", err)

		return status.Error(codes.PermissionDenied, "authorization unavailable")
	}
}

// StreamVitals accepts a continuous device stream. Invalid samples are counted
// and dropped rather than failing the stream — one bad reading from a flaky
// sensor must not disconnect a whole device.
func (s *Server) StreamVitals(stream telemetryv1.VitalsService_StreamVitalsServer) error {
	ctx := stream.Context()

	var accepted, rejected uint64

	// A stream typically carries one device bound to one recipient; cache the
	// allow decision per recipient so a long stream makes one authz call, not
	// one per sample — while still checking every distinct recipient a caller
	// tries to write, so it cannot slip in a sample for someone else.
	allowed := make(map[string]bool)

	for {
		req, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			return stream.SendAndClose(&telemetryv1.StreamVitalsResponse{
				Accepted: accepted,
				Rejected: rejected,
			})
		}
		if err != nil {
			return err
		}

		sample := req.GetSample()

		if err := vitals.Validate(sample, s.now()); err != nil {
			s.log.WarnContext(ctx, "rejected sample",
				"device_id", sample.GetDeviceId(), "error", err)
			rejected++

			continue
		}

		recipient := sample.GetCareRecipientId()
		if !allowed[recipient] {
			if err := s.authorize(ctx, authz.RelationEditor, recipient); err != nil {
				// Authorization failures are terminal for the stream: a caller
				// writing for a recipient it may not touch is not a flaky
				// sensor, it is a rejected identity.
				return err
			}

			allowed[recipient] = true
		}

		if err := s.publisher.Publish(ctx, sample); err != nil {
			// A broker failure is the service's problem, not the device's:
			// surface it so the client can retry the stream.
			s.log.ErrorContext(ctx, "publish failed", "error", err)

			return status.Error(codes.Unavailable, "ingest temporarily unavailable")
		}

		accepted++
	}
}

// PublishVitals is the single-sample path — what REST clients reach through
// the gateway's gRPC transcoding.
func (s *Server) PublishVitals(
	ctx context.Context,
	req *telemetryv1.PublishVitalsRequest,
) (*telemetryv1.PublishVitalsResponse, error) {
	sample := req.GetSample()

	if err := vitals.Validate(sample, s.now()); err != nil {
		return nil, status.Error(codes.InvalidArgument, err.Error())
	}

	if err := s.authorize(ctx, authz.RelationEditor, sample.GetCareRecipientId()); err != nil {
		return nil, err
	}

	if err := s.publisher.Publish(ctx, sample); err != nil {
		s.log.ErrorContext(ctx, "publish failed", "error", err)

		return nil, status.Error(codes.Unavailable, "ingest temporarily unavailable")
	}

	return &telemetryv1.PublishVitalsResponse{Accepted: 1}, nil
}

func (s *Server) GetWindow(
	ctx context.Context,
	req *telemetryv1.GetWindowRequest,
) (*telemetryv1.GetWindowResponse, error) {
	if req.GetCareRecipientId() == "" {
		return nil, status.Error(codes.InvalidArgument, "care_recipient_id is required")
	}

	if err := s.authorize(ctx, authz.RelationViewer, req.GetCareRecipientId()); err != nil {
		return nil, err
	}

	to := s.now()
	if req.GetTo() != nil {
		to = req.GetTo().AsTime()
	}

	from := to.Add(-defaultWindow)
	if req.GetFrom() != nil {
		from = req.GetFrom().AsTime()
	}

	if !from.Before(to) {
		return nil, status.Error(codes.InvalidArgument, "from must be before to")
	}

	samples, err := s.reader.Window(ctx, req.GetCareRecipientId(), from, to, req.GetLimit())
	if err != nil {
		s.log.ErrorContext(ctx, "window query failed", "error", err)

		return nil, status.Error(codes.Internal, "query failed")
	}

	return &telemetryv1.GetWindowResponse{Samples: samples}, nil
}
