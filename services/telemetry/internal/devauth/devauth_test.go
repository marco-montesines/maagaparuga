package devauth_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"maagaparuga/services/telemetry/internal/devauth"
)

func TestStaticReturnsValue(t *testing.T) {
	t.Parallel()

	tok, err := devauth.Static{Value: "pat-123"}.Token(context.Background())
	if err != nil || tok != "pat-123" {
		t.Fatalf("got (%q, %v), want (pat-123, nil)", tok, err)
	}

	if _, err := (devauth.Static{}).Token(context.Background()); err == nil {
		t.Error("empty static token should error")
	}
}

func TestClientCredentialsMintsToken(t *testing.T) {
	t.Parallel()

	var gotAuth, gotBody string

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		_ = r.ParseForm()
		gotBody = r.Form.Encode()
		_, _ = w.Write([]byte(`{"access_token":"at-abc","token_type":"Bearer"}`))
	}))
	defer srv.Close()

	src := devauth.ClientCredentials{
		Issuer: srv.URL, ClientID: "telemetry-device", ClientSecret: "s3cr3t", ProjectID: "999",
		HTTP: srv.Client(),
	}

	tok, err := src.Token(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if tok != "at-abc" {
		t.Errorf("token = %q, want at-abc", tok)
	}

	if gotAuth == "" || !strings.HasPrefix(gotAuth, "Basic ") {
		t.Errorf("expected HTTP basic auth, got %q", gotAuth)
	}
	// The project-audience scope is what makes the token acceptable to the
	// telemetry service; assert it is requested.
	if !strings.Contains(gotBody, "urn%3Azitadel%3Aiam%3Aorg%3Aproject%3Aid%3A999%3Aaud") {
		t.Errorf("project-audience scope missing from request body: %s", gotBody)
	}

	if !strings.Contains(gotBody, "grant_type=client_credentials") {
		t.Errorf("wrong grant type: %s", gotBody)
	}
}

func TestClientCredentialsRequiresConfig(t *testing.T) {
	t.Parallel()

	if _, err := (devauth.ClientCredentials{Issuer: "http://x"}).Token(context.Background()); err == nil {
		t.Error("missing client id/secret/project should error")
	}
}

func TestClientCredentialsSurfacesProviderError(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"error":"invalid_client","error_description":"bad secret"}`))
	}))
	defer srv.Close()

	_, err := devauth.ClientCredentials{
		Issuer: srv.URL, ClientID: "d", ClientSecret: "wrong", ProjectID: "1", HTTP: srv.Client(),
	}.Token(context.Background())
	if err == nil || !strings.Contains(err.Error(), "invalid_client") {
		t.Errorf("expected provider error surfaced, got %v", err)
	}
}
