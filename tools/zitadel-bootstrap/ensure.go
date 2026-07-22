package main

import (
	"context"
	"fmt"
)

// ensureProject returns the id of the named project, creating it if absent.
// This makes the bootstrap safe to re-run — the create path is not idempotent
// on its own (ZITADEL 409s on a duplicate name).
func ensureProject(ctx context.Context, api *client, name string) (string, error) {
	var created struct {
		ID string `json:"id"`
	}

	code, err := api.call(ctx, "/management/v1/projects", map[string]any{
		"name":                 name,
		"projectRoleAssertion": true,
		"projectRoleCheck":     false,
		"hasProjectCheck":      false,
	}, &created)
	if err == nil {
		return created.ID, nil
	}
	if code != 409 {
		return "", fmt.Errorf("create project: %w", err)
	}

	// Already exists — search for it by name.
	var search struct {
		Result []struct {
			ID   string `json:"id"`
			Name string `json:"name"`
		} `json:"result"`
	}
	if _, err := api.call(ctx, "/management/v1/projects/_search", map[string]any{
		"queries": []map[string]any{
			{"nameQuery": map[string]any{"name": name, "method": "TEXT_QUERY_METHOD_EQUALS"}},
		},
	}, &search); err != nil {
		return "", fmt.Errorf("search project: %w", err)
	}

	for _, p := range search.Result {
		if p.Name == name {
			return p.ID, nil
		}
	}

	return "", fmt.Errorf("project %q reported as existing but not found in search", name)
}
