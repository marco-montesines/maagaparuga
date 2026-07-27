package authz_test

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"maagaparuga/services/telemetry/internal/authz"
)

// newClientTo builds a client pointed at a test server.
func newClientTo(t *testing.T, url string) *authz.Client {
	t.Helper()

	c, err := authz.New(authz.Config{URL: url, StoreID: "store-1", ModelID: "model-1"})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	return c
}

func TestCheckAllows(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"allowed": true}`))
	}))
	defer srv.Close()

	if err := newClientTo(t, srv.URL).Check(context.Background(), "1", authz.RelationViewer, "42"); err != nil {
		t.Fatalf("expected allow, got: %v", err)
	}
}

func TestCheckDeniesWhenNotAllowed(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"allowed": false}`))
	}))
	defer srv.Close()

	err := newClientTo(t, srv.URL).Check(context.Background(), "1", authz.RelationEditor, "42")

	if !errors.Is(err, authz.ErrDenied) {
		t.Fatalf("expected ErrDenied, got: %v", err)
	}
}

// A transport or server failure must DENY, never allow — the whole point of
// this layer is that it does not fail open.
func TestCheckFailsClosedOnServerError(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	err := newClientTo(t, srv.URL).Check(context.Background(), "1", authz.RelationViewer, "42")
	if err == nil {
		t.Fatal("a 500 from OpenFGA must not allow")
	}

	if errors.Is(err, authz.ErrDenied) {
		return // ErrDenied is also acceptable — the point is "not nil"
	}
}

func TestCheckFailsClosedWhenUnreachable(t *testing.T) {
	t.Parallel()

	// Nothing listening on this address.
	err := newClientTo(t, "http://127.0.0.1:1").Check(context.Background(), "1", authz.RelationViewer, "42")
	if err == nil {
		t.Fatal("an unreachable OpenFGA must not allow")
	}
}

func TestNewRequiresStore(t *testing.T) {
	t.Parallel()

	if _, err := authz.New(authz.Config{URL: "http://x"}); err == nil {
		t.Fatal("expected an error when store id is missing")
	}
}

// The request the client sends must carry the model's subject/object shape.
func TestCheckSendsExpectedTuple(t *testing.T) {
	t.Parallel()

	var gotUser, gotRelation, gotObject string

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			TupleKey struct {
				User, Relation, Object string
			} `json:"tuple_key"`
		}

		_ = decodeJSON(r, &body)
		gotUser, gotRelation, gotObject = body.TupleKey.User, body.TupleKey.Relation, body.TupleKey.Object

		_, _ = w.Write([]byte(`{"allowed": true}`))
	}))
	defer srv.Close()

	_ = newClientTo(t, srv.URL).Check(context.Background(), "7", authz.RelationEditor, "42")

	if gotUser != "user:7" || gotRelation != "editor" || gotObject != "care_recipient:42" {
		t.Fatalf("unexpected tuple: user=%q relation=%q object=%q", gotUser, gotRelation, gotObject)
	}
}
