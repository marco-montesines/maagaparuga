package authz

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

type checkRequest struct {
	TupleKey struct {
		User     string `json:"user"`
		Relation string `json:"relation"`
		Object   string `json:"object"`
	} `json:"tuple_key"`
	AuthorizationModelID string `json:"authorization_model_id,omitempty"`
}

type checkResponse struct {
	Allowed bool `json:"allowed"`
}

func (c *Client) postCheck(ctx context.Context, endpoint string, body checkRequest) (bool, error) {
	payload, err := json.Marshal(body)
	if err != nil {
		return false, fmt.Errorf("encode request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(payload))
	if err != nil {
		return false, fmt.Errorf("build request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return false, fmt.Errorf("send request: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		// Read a bounded amount of the body for context, then deny.
		snippet, _ := io.ReadAll(io.LimitReader(resp.Body, 512))

		return false, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, snippet)
	}

	var decoded checkResponse
	if err := json.NewDecoder(resp.Body).Decode(&decoded); err != nil {
		return false, fmt.Errorf("decode response: %w", err)
	}

	return decoded.Allowed, nil
}
