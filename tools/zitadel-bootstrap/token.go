package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// serviceAccountKey is ZITADEL's machine-key JSON (type 1).
type serviceAccountKey struct {
	Type   string `json:"type"`
	KeyID  string `json:"keyId"`
	Key    string `json:"key"` // PEM RSA private key
	UserID string `json:"userId"`
}

func loadKey(path string) (*serviceAccountKey, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read key file: %w", err)
	}

	var key serviceAccountKey
	if err := json.Unmarshal(raw, &key); err != nil {
		return nil, fmt.Errorf("parse key file: %w", err)
	}

	if key.KeyID == "" || key.Key == "" || key.UserID == "" {
		return nil, fmt.Errorf("key file missing keyId/key/userId")
	}

	return &key, nil
}

// accessToken performs the JWT-profile grant: sign a short-lived assertion
// with the service account's private key, exchange it for an access token
// scoped to manage the ZITADEL instance.
func accessToken(ctx context.Context, endpoint, issuer string, key *serviceAccountKey) (string, error) {
	signKey, err := jwt.ParseRSAPrivateKeyFromPEM([]byte(key.Key))
	if err != nil {
		return "", fmt.Errorf("parse private key: %w", err)
	}

	now := time.Now()
	assertion := jwt.NewWithClaims(jwt.SigningMethodRS256, jwt.MapClaims{
		"iss": key.UserID,
		"sub": key.UserID,
		"aud": issuer,
		"iat": now.Unix(),
		"exp": now.Add(time.Hour).Unix(),
	})
	assertion.Header["kid"] = key.KeyID

	signed, err := assertion.SignedString(signKey)
	if err != nil {
		return "", fmt.Errorf("sign assertion: %w", err)
	}

	form := url.Values{
		"grant_type": {"urn:ietf:params:oauth:grant-type:jwt-bearer"},
		"assertion":  {signed},
		"scope": {strings.Join([]string{
			"openid",
			"urn:zitadel:iam:org:project:id:zitadel:aud", // manage the instance
		}, " ")},
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		endpoint+"/oauth/v2/token", strings.NewReader(form.Encode()))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	// ZITADEL routes by Host; present the issuer host even when dialing the
	// in-cluster endpoint.
	if h := hostOf(issuer); h != "" {
		req.Host = h
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("token request: %w", err)
	}
	defer resp.Body.Close()

	var body struct {
		AccessToken string `json:"access_token"`
		Error       string `json:"error"`
		Description string `json:"error_description"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		return "", fmt.Errorf("decode token response: %w", err)
	}

	if resp.StatusCode != http.StatusOK || body.AccessToken == "" {
		return "", fmt.Errorf("token exchange failed (%d): %s %s",
			resp.StatusCode, body.Error, body.Description)
	}

	return body.AccessToken, nil
}

// hostOf extracts host[:port] from a URL for use as an HTTP Host header.
func hostOf(raw string) string {
	u, err := url.Parse(raw)
	if err != nil {
		return ""
	}

	return u.Host
}
