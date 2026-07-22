// Package authz answers the question the authentication layer cannot: not
// "is this token real?" but "may THIS caller touch THIS care recipient?".
//
// It checks OpenFGA relationships (ADR 0009) — the same model the web app
// enforces (`viewer` to read, `editor` to write) — so a valid token cannot
// read or write vitals for a care recipient it has no relationship with.
// Without this, authentication alone lets any token reach every recipient's
// data: the exact object-level access flaw (BOLA/IDOR) this guards against.
package authz

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"time"
)

// Relations mirror fga/model.fga.
const (
	RelationViewer = "viewer" // read a care recipient's data
	RelationEditor = "editor" // write clinical content (staff only)
)

// ErrDenied is returned when the relationship does not hold. Transport and
// configuration failures are returned as wrapped errors and MUST be treated
// as denials by callers — this package never fails open.
var ErrDenied = errors.New("authorization denied")

// Checker is the seam the server depends on; the concrete Client talks to
// OpenFGA, tests supply a fake.
type Checker interface {
	// Check reports whether `subject` has `relation` on
	// care_recipient:`careRecipientID`. A nil error means allowed; ErrDenied
	// (or any other error) means the caller must refuse the operation.
	Check(ctx context.Context, subject, relation, careRecipientID string) error
}

// Client is a minimal OpenFGA check client. It holds only configuration, so
// it is safe to share across goroutines.
type Client struct {
	httpClient *http.Client
	url        string
	storeID    string
	modelID    string
}

// Config carries the OpenFGA coordinates.
type Config struct {
	URL     string
	StoreID string
	ModelID string
	Timeout time.Duration
}

func New(cfg Config) (*Client, error) {
	if cfg.URL == "" {
		return nil, errors.New("openfga url is required")
	}
	if cfg.StoreID == "" {
		return nil, errors.New("openfga store id is required")
	}

	timeout := cfg.Timeout
	if timeout == 0 {
		timeout = 2 * time.Second
	}

	return &Client{
		httpClient: &http.Client{Timeout: timeout},
		url:        trimSlash(cfg.URL),
		storeID:    cfg.StoreID,
		modelID:    cfg.ModelID,
	}, nil
}

// Check queries the OpenFGA check endpoint. Any non-allow outcome — a false
// result, a non-2xx status, a transport error, a decode error — denies.
func (c *Client) Check(ctx context.Context, subject, relation, careRecipientID string) error {
	body := checkRequest{
		AuthorizationModelID: c.modelID,
	}
	body.TupleKey.User = "user:" + subject
	body.TupleKey.Relation = relation
	body.TupleKey.Object = "care_recipient:" + careRecipientID

	endpoint := fmt.Sprintf("%s/stores/%s/check", c.url, c.storeID)

	allowed, err := c.postCheck(ctx, endpoint, body)
	if err != nil {
		return fmt.Errorf("openfga check: %w", err)
	}

	if !allowed {
		return ErrDenied
	}

	return nil
}

func trimSlash(s string) string {
	for len(s) > 0 && s[len(s)-1] == '/' {
		s = s[:len(s)-1]
	}

	return s
}
