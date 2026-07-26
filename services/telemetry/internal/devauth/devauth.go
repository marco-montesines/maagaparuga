// Package devauth obtains the bearer token a (mock) IoMT device presents to
// the telemetry ingest API. The telemetry service verifies only that the token
// is a ZITADEL-signed JWT with the right issuer and audience (see package
// auth); it does not care HOW the device obtained it. Real device fleets differ
// widely, so this package offers several onboarding methods behind one seam:
//
//	client_credentials  OAuth2 M2M — device holds a client id + secret (default)
//	jwt_profile         device holds a private key and signs an assertion
//	static              a pre-minted bearer token (e.g. a personal access token)
//
// All three yield the same thing: a short-lived access token whose audience is
// the MaagapAruga project, requested via ZITADEL's reserved project-audience
// scope so the token validates at the telemetry service.
package devauth

import (
	"context"
	"crypto/rsa"
	"crypto/x509"
	"encoding/json"
	"encoding/pem"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	jose "github.com/go-jose/go-jose/v4"
)

// TokenSource yields a bearer token for a device. Implementations may cache or
// re-mint; callers should fetch once per stream.
type TokenSource interface {
	Token(ctx context.Context) (string, error)
}

// projectAudienceScope is ZITADEL's reserved scope that puts a project id into
// the access token's `aud`, so the telemetry service (which expects the project
// as its audience) accepts it.
func projectAudienceScope(projectID string) string {
	return "urn:zitadel:iam:org:project:id:" + projectID + ":aud"
}

// Static returns a fixed, pre-minted token — a ZITADEL personal access token
// (PAT) or any bearer token supplied out of band. The simplest onboarding: no
// exchange happens at run time.
type Static struct{ Value string }

// Token returns the pre-minted token, or an error if none was configured.
func (s Static) Token(context.Context) (string, error) {
	if s.Value == "" {
		return "", errors.New("static token is empty")
	}

	return s.Value, nil
}

// ClientCredentials mints a token via the OAuth2 client-credentials grant — the
// standard machine-to-machine flow, and the default for provisioned devices.
type ClientCredentials struct {
	Issuer       string // ZITADEL issuer, e.g. http://maagaparuga.test:9080
	ClientID     string // the device's client id (machine user name)
	ClientSecret string
	ProjectID    string // audience: the MaagapAruga project id
	HTTP         *http.Client
}

// Token requests an access token via the OAuth2 client-credentials grant.
func (c ClientCredentials) Token(ctx context.Context) (string, error) {
	if c.Issuer == "" || c.ClientID == "" || c.ClientSecret == "" || c.ProjectID == "" {
		return "", errors.New("client_credentials needs issuer, client id, secret and project id")
	}

	form := url.Values{
		"grant_type": {"client_credentials"},
		"scope":      {"openid " + projectAudienceScope(c.ProjectID)},
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		strings.TrimRight(c.Issuer, "/")+"/oauth/v2/token", strings.NewReader(form.Encode()))
	if err != nil {
		return "", fmt.Errorf("build token request: %w", err)
	}

	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.SetBasicAuth(c.ClientID, c.ClientSecret)

	return doTokenRequest(c.httpClient(), req)
}

func (c ClientCredentials) httpClient() *http.Client {
	if c.HTTP != nil {
		return c.HTTP
	}

	return http.DefaultClient
}

// JWTProfile mints a token by signing a JWT assertion with the device's private
// key (the JWT-profile / urn:ietf:params:oauth:grant-type:jwt-bearer grant). No
// secret crosses the wire; the device proves possession of the key. KeyPath is
// a ZITADEL machine-key JSON file (type, keyId, key PEM, userId).
type JWTProfile struct {
	Issuer    string
	KeyPath   string
	ProjectID string
	HTTP      *http.Client
	now       func() time.Time // test seam
}

// machineKey is ZITADEL's machine-key JSON.
type machineKey struct {
	KeyID  string `json:"keyId"`
	Key    string `json:"key"` // PEM RSA private key
	UserID string `json:"userId"`
}

// Token signs a JWT assertion with the device key and exchanges it for an
// access token via the JWT-bearer grant.
func (j JWTProfile) Token(ctx context.Context) (string, error) {
	if j.Issuer == "" || j.KeyPath == "" || j.ProjectID == "" {
		return "", errors.New("jwt_profile needs issuer, key path and project id")
	}

	key, err := loadMachineKey(j.KeyPath)
	if err != nil {
		return "", err
	}

	assertion, err := j.signAssertion(key)
	if err != nil {
		return "", err
	}

	form := url.Values{
		"grant_type": {"urn:ietf:params:oauth:grant-type:jwt-bearer"},
		"assertion":  {assertion},
		"scope":      {"openid " + projectAudienceScope(j.ProjectID)},
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		strings.TrimRight(j.Issuer, "/")+"/oauth/v2/token", strings.NewReader(form.Encode()))
	if err != nil {
		return "", fmt.Errorf("build token request: %w", err)
	}

	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	client := j.HTTP
	if client == nil {
		client = http.DefaultClient
	}

	return doTokenRequest(client, req)
}

func (j JWTProfile) signAssertion(key *machineKey) (string, error) {
	priv, err := parseRSAPrivateKey(key.Key)
	if err != nil {
		return "", err
	}

	signer, err := jose.NewSigner(
		jose.SigningKey{Algorithm: jose.RS256, Key: priv},
		(&jose.SignerOptions{}).WithType("JWT").WithHeader("kid", key.KeyID),
	)
	if err != nil {
		return "", fmt.Errorf("build signer: %w", err)
	}

	now := time.Now
	if j.now != nil {
		now = j.now
	}

	t := now()

	// The assertion is addressed to the issuer; ZITADEL exchanges it for an
	// access token carrying the requested project audience.
	claims := map[string]any{
		"iss": key.UserID,
		"sub": key.UserID,
		"aud": strings.TrimRight(j.Issuer, "/"),
		"iat": t.Unix(),
		"exp": t.Add(time.Hour).Unix(),
	}

	payload, err := json.Marshal(claims)
	if err != nil {
		return "", fmt.Errorf("marshal claims: %w", err)
	}

	jws, err := signer.Sign(payload)
	if err != nil {
		return "", fmt.Errorf("sign assertion: %w", err)
	}

	serialized, err := jws.CompactSerialize()
	if err != nil {
		return "", fmt.Errorf("serialize assertion: %w", err)
	}

	return serialized, nil
}

func loadMachineKey(path string) (*machineKey, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read key file: %w", err)
	}

	var key machineKey
	if err := json.Unmarshal(raw, &key); err != nil {
		return nil, fmt.Errorf("parse key file: %w", err)
	}

	if key.KeyID == "" || key.Key == "" || key.UserID == "" {
		return nil, errors.New("key file missing keyId/key/userId")
	}

	return &key, nil
}

func parseRSAPrivateKey(pemStr string) (*rsa.PrivateKey, error) {
	block, _ := pem.Decode([]byte(pemStr))
	if block == nil {
		return nil, errors.New("no PEM block in private key")
	}

	if key, err := x509.ParsePKCS1PrivateKey(block.Bytes); err == nil {
		return key, nil
	}

	parsed, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("parse private key: %w", err)
	}

	rsaKey, ok := parsed.(*rsa.PrivateKey)
	if !ok {
		return nil, errors.New("private key is not RSA")
	}

	return rsaKey, nil
}

// doTokenRequest performs the token request and extracts the access token,
// surfacing ZITADEL's error without echoing the token on failure.
func doTokenRequest(client *http.Client, req *http.Request) (string, error) {
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("token request: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	body, _ := io.ReadAll(resp.Body)

	var parsed struct {
		AccessToken string `json:"access_token"`
		Error       string `json:"error"`
		Description string `json:"error_description"`
	}
	if err := json.Unmarshal(body, &parsed); err != nil {
		return "", fmt.Errorf("decode token response (%d): %w", resp.StatusCode, err)
	}

	if resp.StatusCode != http.StatusOK || parsed.AccessToken == "" {
		return "", fmt.Errorf("token exchange failed (%d): %s %s",
			resp.StatusCode, parsed.Error, parsed.Description)
	}

	return parsed.AccessToken, nil
}
