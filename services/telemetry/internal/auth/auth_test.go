package auth_test

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"errors"
	"log/slog"
	"strconv"
	"testing"
	"time"

	"github.com/coreos/go-oidc/v3/oidc"
	jose "github.com/go-jose/go-jose/v4"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	"maagaparuga/services/telemetry/internal/auth"
)

const (
	issuer   = "https://zitadel.example.com"
	audience = "telemetry"
)

// signer mints tokens the way the identity provider would, so the tests
// exercise real signature verification rather than a stub.
type signer struct {
	key *rsa.PrivateKey
}

func newSigner(t *testing.T) *signer {
	t.Helper()

	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("generate key: %v", err)
	}

	return &signer{key: key}
}

func (s *signer) sign(t *testing.T, claims string) string {
	t.Helper()

	jws, err := jose.NewSigner(
		jose.SigningKey{Algorithm: jose.RS256, Key: s.key},
		(&jose.SignerOptions{}).WithType("JWT"),
	)
	if err != nil {
		t.Fatalf("new signer: %v", err)
	}

	signed, err := jws.Sign([]byte(claims))
	if err != nil {
		t.Fatalf("sign: %v", err)
	}

	compact, err := signed.CompactSerialize()
	if err != nil {
		t.Fatalf("serialize: %v", err)
	}

	return compact
}

// keySet is the verifier's view of the provider's public keys.
func (s *signer) keySet() oidc.KeySet {
	return &oidc.StaticKeySet{PublicKeys: []crypto.PublicKey{&s.key.PublicKey}}
}

func TestVerify(t *testing.T) {
	t.Parallel()

	valid := newSigner(t)
	attacker := newSigner(t)

	future := time.Now().Add(time.Hour).Unix()
	past := time.Now().Add(-time.Hour).Unix()

	tests := []struct {
		name    string
		token   func(t *testing.T) string
		wantErr error
	}{
		{
			name: "well formed token",
			token: func(t *testing.T) string {
				return valid.sign(t, `{"sub":"device-1","iss":"`+issuer+
					`","aud":["telemetry"],"exp":`+strconv.FormatInt(future, 10)+`}`)
			},
		},
		{
			name: "audience may be a bare string",
			token: func(t *testing.T) string {
				return valid.sign(t, `{"sub":"device-1","iss":"`+issuer+
					`","aud":"telemetry","exp":`+strconv.FormatInt(future, 10)+`}`)
			},
		},
		{
			name: "signed by someone else",
			token: func(t *testing.T) string {
				return attacker.sign(t, `{"sub":"device-1","iss":"`+issuer+
					`","aud":"telemetry","exp":`+strconv.FormatInt(future, 10)+`}`)
			},
			wantErr: auth.ErrBadSignature,
		},
		{
			name: "issued by another provider",
			token: func(t *testing.T) string {
				return valid.sign(t, `{"sub":"device-1","iss":"https://evil.example.com",`+
					`"aud":"telemetry","exp":`+strconv.FormatInt(future, 10)+`}`)
			},
			wantErr: auth.ErrWrongIssuer,
		},
		{
			name: "minted for a different service",
			token: func(t *testing.T) string {
				return valid.sign(t, `{"sub":"device-1","iss":"`+issuer+
					`","aud":"some-other-service","exp":`+strconv.FormatInt(future, 10)+`}`)
			},
			wantErr: auth.ErrWrongAudience,
		},
		{
			name: "expired",
			token: func(t *testing.T) string {
				return valid.sign(t, `{"sub":"device-1","iss":"`+issuer+
					`","aud":"telemetry","exp":`+strconv.FormatInt(past, 10)+`}`)
			},
			wantErr: auth.ErrExpired,
		},
	}

	verifier := auth.NewVerifierWithKeySet(valid.keySet(), issuer, audience)

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()

			claims, err := verifier.Verify(context.Background(), tt.token(t))

			if tt.wantErr != nil {
				if !errors.Is(err, tt.wantErr) {
					t.Fatalf("got error %v, want %v", err, tt.wantErr)
				}

				return
			}

			if err != nil {
				t.Fatalf("expected token to verify, got: %v", err)
			}

			if claims.Subject != "device-1" {
				t.Errorf("subject = %q, want device-1", claims.Subject)
			}
		})
	}
}

func TestBearerToken(t *testing.T) {
	t.Parallel()

	tests := []struct {
		header  string
		want    string
		wantErr bool
	}{
		{header: "Bearer abc.def.ghi", want: "abc.def.ghi"},
		{header: "bearer abc.def.ghi", want: "abc.def.ghi"}, // scheme is case-insensitive
		{header: "abc.def.ghi", wantErr: true},              // no scheme
		{header: "Bearer ", wantErr: true},
		{header: "", wantErr: true},
		{header: "Basic dXNlcjpwYXNz", wantErr: true},
	}

	for _, tt := range tests {
		t.Run(tt.header, func(t *testing.T) {
			t.Parallel()

			got, err := auth.BearerToken(tt.header)

			if tt.wantErr {
				if err == nil {
					t.Fatalf("expected error for %q", tt.header)
				}

				return
			}

			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			if got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

type stubVerifier struct{ err error }

func (s stubVerifier) Verify(context.Context, string) (*auth.Claims, error) {
	if s.err != nil {
		return nil, s.err
	}

	return &auth.Claims{Subject: "device-1"}, nil
}

func newInterceptors(err error) *auth.Interceptors {
	return &auth.Interceptors{
		Verifier: stubVerifier{err: err},
		Log:      slog.New(slog.DiscardHandler),
		Public:   map[string]bool{"/grpc.health.v1.Health/Check": true},
	}
}

func TestUnaryInterceptorRejectsUnauthenticatedCalls(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name string
		ctx  context.Context
		err  error
	}{
		{name: "no metadata", ctx: context.Background()},
		{
			name: "no authorization header",
			ctx:  metadata.NewIncomingContext(context.Background(), metadata.MD{}),
		},
		{
			name: "malformed header",
			ctx: metadata.NewIncomingContext(context.Background(),
				metadata.Pairs("authorization", "no-scheme-here")),
		},
		{
			name: "verifier rejects the token",
			ctx: metadata.NewIncomingContext(context.Background(),
				metadata.Pairs("authorization", "Bearer bad.token")),
			err: auth.ErrBadSignature,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()

			called := false
			handler := func(context.Context, any) (any, error) {
				called = true

				return nil, nil
			}

			_, err := newInterceptors(tt.err).Unary()(tt.ctx, nil,
				&grpc.UnaryServerInfo{FullMethod: "/svc/Method"}, handler)

			if status.Code(err) != codes.Unauthenticated {
				t.Fatalf("got %v, want Unauthenticated", status.Code(err))
			}

			if called {
				t.Error("handler must not run for an unauthenticated call")
			}
		})
	}
}

func TestUnaryInterceptorPassesClaimsThrough(t *testing.T) {
	t.Parallel()

	ctx := metadata.NewIncomingContext(context.Background(),
		metadata.Pairs("authorization", "Bearer good.token"))

	var seen *auth.Claims

	handler := func(ctx context.Context, _ any) (any, error) {
		seen, _ = auth.ClaimsFrom(ctx)

		return nil, nil
	}

	if _, err := newInterceptors(nil).Unary()(ctx, nil,
		&grpc.UnaryServerInfo{FullMethod: "/svc/Method"}, handler); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if seen == nil || seen.Subject != "device-1" {
		t.Fatal("handler did not receive the verified claims")
	}
}

// Health checks must stay reachable: kubelet probes carry no credentials.
func TestPublicMethodsSkipAuthentication(t *testing.T) {
	t.Parallel()

	called := false
	handler := func(context.Context, any) (any, error) {
		called = true

		return nil, nil
	}

	_, err := newInterceptors(auth.ErrBadSignature).Unary()(context.Background(), nil,
		&grpc.UnaryServerInfo{FullMethod: "/grpc.health.v1.Health/Check"}, handler)
	if err != nil {
		t.Fatalf("health check must not require credentials: %v", err)
	}

	if !called {
		t.Error("handler should have run")
	}
}
