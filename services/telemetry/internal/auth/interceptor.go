package auth

import (
	"context"
	"log/slog"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

// TokenVerifier is the seam the interceptors depend on.
type TokenVerifier interface {
	Verify(ctx context.Context, rawToken string) (*Claims, error)
}

type claimsKey struct{}

// ClaimsFrom returns the verified claims attached to an authenticated call.
func ClaimsFrom(ctx context.Context) (*Claims, bool) {
	claims, ok := ctx.Value(claimsKey{}).(*Claims)

	return claims, ok
}

// ContextWithClaims attaches verified claims to a context. The interceptor
// uses it after a successful verification; downstream packages and tests use
// it to construct an authenticated context.
func ContextWithClaims(ctx context.Context, claims *Claims) context.Context {
	return context.WithValue(ctx, claimsKey{}, claims)
}

// Interceptors enforces authentication on every RPC except the ones named in
// Public (the gRPC health service, so Kubernetes probes need no credentials).
//
// There is no "allow when the verifier is unavailable" path: a call without a
// verifiable token is Unauthenticated.
type Interceptors struct {
	Verifier TokenVerifier
	Log      *slog.Logger
	Public   map[string]bool
}

// Unary returns a unary interceptor that authenticates every RPC except the
// Public ones.
func (i *Interceptors) Unary() grpc.UnaryServerInterceptor {
	return func(
		ctx context.Context,
		req any,
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (any, error) {
		if i.Public[info.FullMethod] {
			return handler(ctx, req)
		}

		authenticated, err := i.authenticate(ctx, info.FullMethod)
		if err != nil {
			return nil, err
		}

		return handler(authenticated, req)
	}
}

// Stream returns a streaming interceptor that authenticates every stream except
// the Public ones.
func (i *Interceptors) Stream() grpc.StreamServerInterceptor {
	return func(
		srv any,
		stream grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {
		if i.Public[info.FullMethod] {
			return handler(srv, stream)
		}

		authenticated, err := i.authenticate(stream.Context(), info.FullMethod)
		if err != nil {
			return err
		}

		return handler(srv, &wrappedStream{ServerStream: stream, ctx: authenticated})
	}
}

func (i *Interceptors) authenticate(ctx context.Context, method string) (context.Context, error) {
	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		return nil, status.Error(codes.Unauthenticated, "missing credentials")
	}

	values := md.Get("authorization")
	if len(values) == 0 {
		return nil, status.Error(codes.Unauthenticated, "missing credentials")
	}

	token, err := BearerToken(values[0])
	if err != nil {
		return nil, status.Error(codes.Unauthenticated, "malformed credentials")
	}

	claims, err := i.Verifier.Verify(ctx, token)
	if err != nil {
		// Log the reason for operators; tell the caller only that it failed.
		i.Log.WarnContext(ctx, "rejected call", "method", method, "reason", err)

		return nil, status.Error(codes.Unauthenticated, "invalid credentials")
	}

	return ContextWithClaims(ctx, claims), nil
}

// wrappedStream carries the authenticated context to the handler, since
// grpc.ServerStream's context is fixed at creation.
type wrappedStream struct {
	grpc.ServerStream

	ctx context.Context
}

func (w *wrappedStream) Context() context.Context { return w.ctx }
