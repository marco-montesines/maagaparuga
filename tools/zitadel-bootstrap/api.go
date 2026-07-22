package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

// client wraps the ZITADEL Management/Admin REST API with a bearer token.
type client struct {
	base  string
	token string
	http  *http.Client
}

func newClient(base, token string) *client {
	return &client{base: base, token: token, http: http.DefaultClient}
}

// call POSTs a JSON body and decodes the JSON response. ZITADEL's create
// endpoints are idempotent-unfriendly (they error on duplicates), so callers
// tolerate AlreadyExists via the returned status.
func (c *client) call(ctx context.Context, path string, in, out any) (int, error) {
	var payload []byte
	if in != nil {
		var err error
		if payload, err = json.Marshal(in); err != nil {
			return 0, fmt.Errorf("encode %s: %w", path, err)
		}
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		c.base+path, bytes.NewReader(payload))
	if err != nil {
		return 0, err
	}
	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(req)
	if err != nil {
		return 0, fmt.Errorf("call %s: %w", path, err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	if resp.StatusCode >= 400 {
		// Surface the ZITADEL error message; the caller decides whether an
		// AlreadyExists (409) is fatal.
		return resp.StatusCode, fmt.Errorf("%s -> %d: %s", path, resp.StatusCode, body)
	}

	if out != nil && len(body) > 0 {
		if err := json.Unmarshal(body, out); err != nil {
			return resp.StatusCode, fmt.Errorf("decode %s response: %w", path, err)
		}
	}

	return resp.StatusCode, nil
}
