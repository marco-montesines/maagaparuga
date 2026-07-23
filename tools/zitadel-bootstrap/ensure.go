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

// ensureMachineUser returns the id of a machine (service-account) user by
// userName, creating it if absent. Like ensureProject, this keeps the bootstrap
// re-runnable: ZITADEL 409s on a duplicate userName, so on the second run we
// look the existing account up instead of failing.
func ensureMachineUser(ctx context.Context, api *client, userName, name, description string) (string, error) {
	var created struct {
		UserID string `json:"userId"`
	}

	code, err := api.call(ctx, "/management/v1/users/machine", map[string]any{
		"userName":        userName,
		"name":            name,
		"description":     description,
		"accessTokenType": "ACCESS_TOKEN_TYPE_JWT",
	}, &created)
	if err == nil {
		return created.UserID, nil
	}
	if code != 409 {
		return "", fmt.Errorf("create machine user %q: %w", userName, err)
	}

	// Already exists — search for it by userName.
	var search struct {
		Result []struct {
			ID       string `json:"id"`
			UserName string `json:"userName"`
		} `json:"result"`
	}
	if _, err := api.call(ctx, "/management/v1/users/_search", map[string]any{
		"queries": []map[string]any{
			{"userNameQuery": map[string]any{"userName": userName, "method": "TEXT_QUERY_METHOD_EQUALS"}},
		},
	}, &search); err != nil {
		return "", fmt.Errorf("search machine user: %w", err)
	}

	for _, u := range search.Result {
		if u.UserName == userName {
			return u.ID, nil
		}
	}

	return "", fmt.Errorf("machine user %q reported as existing but not found in search", userName)
}
