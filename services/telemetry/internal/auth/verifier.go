// Package auth verifies the JWT access tokens that (mock) devices present
// when streaming vitals. Tokens are issued by ZITADEL (ADR 0009); signatures
// are checked locally against its JWKS, so ingest costs no network round trip
// per request.
package auth

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/coreos/go-oidc/v3/oidc"
)

// Sentinel errors returned when a presented token fails a verification step.
var (
	ErrNoToken       = errors.New("no bearer token presented")
	ErrBadSignature  = errors.New("token signature is not valid")
	ErrWrongIssuer   = errors.New("token issued by an unexpected issuer")
	ErrWrongAudience = errors.New("token is not addressed to this service")
	ErrExpired       = errors.New("token has expired")
)

// Claims are the parts of a verified token this service acts on.
type Claims struct {
	Subject  string
	Issuer   string
	Audience []string
	Expiry   time.Time
}

// Verifier checks tokens against a remote JWKS. The key set is cached and
// refreshed by the OIDC library, so a running service survives key rotation
// without a restart.
type Verifier struct {
	keys     oidc.KeySet
	issuer   string
	audience string
	now      func() time.Time
}

// NewVerifier builds a verifier for an issuer, discovering its JWKS endpoint.
// audience is the identifier this service is registered under; a token minted
// for another service is rejected even if the signature is good.
func NewVerifier(ctx context.Context, issuer, audience string) (*Verifier, error) {
	provider, err := oidc.NewProvider(ctx, issuer)
	if err != nil {
		return nil, fmt.Errorf("discover issuer %q: %w", issuer, err)
	}

	var meta struct {
		JWKSURL string `json:"jwks_uri"`
	}

	if err := provider.Claims(&meta); err != nil {
		return nil, fmt.Errorf("read issuer metadata: %w", err)
	}

	return &Verifier{
		keys:     oidc.NewRemoteKeySet(ctx, meta.JWKSURL),
		issuer:   issuer,
		audience: audience,
		now:      time.Now,
	}, nil
}

// NewVerifierWithKeySet is the seam used by tests and by callers that already
// hold a key set.
func NewVerifierWithKeySet(keys oidc.KeySet, issuer, audience string) *Verifier {
	return &Verifier{keys: keys, issuer: issuer, audience: audience, now: time.Now}
}

// Verify checks the signature first, then the claims. Signature failures are
// reported as such without echoing token contents.
func (v *Verifier) Verify(ctx context.Context, rawToken string) (*Claims, error) {
	payload, err := v.keys.VerifySignature(ctx, rawToken)
	if err != nil {
		return nil, ErrBadSignature
	}

	var body struct {
		Subject  string      `json:"sub"`
		Issuer   string      `json:"iss"`
		Audience audienceSet `json:"aud"`
		Expiry   int64       `json:"exp"`
	}

	if err := json.Unmarshal(payload, &body); err != nil {
		return nil, fmt.Errorf("decode token claims: %w", err)
	}

	if body.Issuer != v.issuer {
		return nil, ErrWrongIssuer
	}

	if v.audience != "" && !body.Audience.contains(v.audience) {
		return nil, ErrWrongAudience
	}

	expiry := time.Unix(body.Expiry, 0)
	if !expiry.After(v.now()) {
		return nil, ErrExpired
	}

	return &Claims{
		Subject:  body.Subject,
		Issuer:   body.Issuer,
		Audience: body.Audience,
		Expiry:   expiry,
	}, nil
}

// audienceSet handles the JWT quirk that "aud" is either a string or an array.
type audienceSet []string

func (a *audienceSet) UnmarshalJSON(data []byte) error {
	var single string
	if err := json.Unmarshal(data, &single); err == nil {
		*a = audienceSet{single}

		return nil
	}

	var many []string
	if err := json.Unmarshal(data, &many); err != nil {
		return fmt.Errorf("aud is neither string nor array: %w", err)
	}

	*a = many

	return nil
}

func (a audienceSet) contains(want string) bool {
	for _, got := range a {
		if got == want {
			return true
		}
	}

	return false
}

// BearerToken extracts the credential from an Authorization header value.
func BearerToken(header string) (string, error) {
	const prefix = "Bearer "

	if len(header) <= len(prefix) || !strings.EqualFold(header[:len(prefix)], prefix) {
		return "", ErrNoToken
	}

	token := strings.TrimSpace(header[len(prefix):])
	if token == "" {
		return "", ErrNoToken
	}

	return token, nil
}
