// Command zitadel-bootstrap performs the one-time, install-time CONFIGURATION
// of a fresh ZITADEL instance for MaagapAruga: the project and its six roles,
// the web OIDC application, and a telemetry service account for device tokens.
//
// It does NOT create human admins — a real deployment's admin comes from
// ZITADEL's first-instance human-admin (operator-supplied email + temporary
// password, password-change-required), and that admin creates everyone else.
// The fictitious users below are opt-in mock data (-seed-mock-users, default
// off): dev turns it on automatically, and an operator can turn it on
// deliberately in ANY environment — including production — to validate a real
// deployment with disposable data, then remove it.
//
// Authenticates with the admin service-account key ZITADEL writes on
// first-instance init, and drives the Management API. Install-time only: it
// runs once and is idle thereafter (kept in the repo for reproducible
// installs, like a migration). Re-running needs a fresh instance because OIDC
// client secrets are shown only at creation.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"time"
)

// Role keys mirror App\Enums\Role — the token's project-roles claim maps
// directly onto the web app's Role enum.
var roles = []struct{ key, name string }{
	{"administrator", "Administrator"},
	{"doctor", "Doctor"},
	{"nurse", "Nurse"},
	{"transcriptionist", "Medical Transcriptionist"},
	{"care_provider", "Care Provider"},
	{"care_recipient", "Care Recipient"},
}

// Mock personas — same emails as DatabaseSeeder::seedStaff so the web app's
// email match on first login binds the seeded row to the ZITADEL subject.
var users = []struct {
	email, first, last, role string
}{
	{"admin@example.com", "Amara", "Demo Santos", "administrator"},
	{"l.reyes@example.com", "Liwayway", "Demo Reyes", "doctor"},
	{"b.cruz@example.com", "Bayani", "Demo Cruz", "doctor"},
	{"l.bautista@example.com", "Ligaya", "Demo Bautista", "nurse"},
	{"k.villanueva@example.com", "Katala", "Demo Villanueva", "transcriptionist"},
	{"t.ocampo@example.com", "Tala", "Demo Ocampo", "care_provider"},
	{"d.salazar@example.com", "Diwa", "Demo Salazar", "care_provider"},
}

type output struct {
	ProjectID             string `json:"project_id"`
	WebClientID           string `json:"web_client_id"`
	WebClientSecret       string `json:"web_client_secret"`
	TelemetryUserID       string `json:"telemetry_user_id"`
	TelemetryClientID     string `json:"telemetry_client_id"`
	TelemetryClientSecret string `json:"telemetry_client_secret"`
	TelemetryProjectID    string `json:"telemetry_project_id"`
}

func main() {
	issuer := flag.String("issuer", env("ZITADEL_ISSUER", "http://localhost:8080"), "ZITADEL issuer URL (token audience + Host header)")
	endpoint := flag.String("endpoint", env("ZITADEL_ENDPOINT", ""), "where to reach ZITADEL (default: the issuer). Set to the in-cluster address to bypass the public gateway")
	keyPath := flag.String("key", env("ZITADEL_KEY_PATH", "/machinekey/admin-sa.json"), "admin service-account key file")
	redirect := flag.String("redirect", env("WEB_REDIRECT_URI", "http://localhost:9080/auth/callback"), "web app OIDC redirect URI")
	postLogout := flag.String("post-logout", env("WEB_POST_LOGOUT_URI", "http://localhost:9080/"), "web app post-logout redirect")
	userPassword := flag.String("user-password", env("MOCK_USER_PASSWORD", "Password1!"), "shared dev password for mock users")
	outPath := flag.String("out", env("OUT_PATH", ""), "write result JSON here (also printed to stdout)")
	// Mock users are demonstration seed data, NOT install configuration. A real
	// deployment leaves this off and creates its own admin in the ZITADEL
	// dashboard; dev/demo turns it on for immediately-usable fictitious logins.
	seedUsers := flag.Bool("seed-mock-users", envBool("SEED_MOCK_USERS", false),
		"also create the fictitious mock users (opt-in for dev, and for validating any deployment)")
	flag.Parse()

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	target := *endpoint
	if target == "" {
		target = *issuer
	}

	if err := run(ctx, *issuer, target, *keyPath, *redirect, *postLogout, *userPassword, *outPath, *seedUsers); err != nil {
		log.Fatalf("bootstrap failed: %v", err)
	}
}

func run(ctx context.Context, issuer, endpoint, keyPath, redirect, postLogout, userPassword, outPath string, seedUsers bool) error {
	key, err := loadKey(keyPath)
	if err != nil {
		return err
	}

	// Dial `endpoint`, but present `issuer` as the audience and Host so ZITADEL
	// routes to the right instance and the token validates — this lets the
	// bootstrap reach ZITADEL directly in-cluster without the admin API being
	// exposed through the public gateway.
	token, err := accessToken(ctx, endpoint, issuer, key)
	if err != nil {
		return err
	}

	api := newClient(endpoint, issuer, token)
	out := output{}

	// 0. Use the built-in (legacy) login UI. ZITADEL v4 defaults new instances
	// to "Login V2", which is a SEPARATE deployment we do not run; without it,
	// the authorize endpoint redirects to /ui/v2/login and 404s. Disabling the
	// feature makes authorize use the self-contained /ui/login served by the
	// ZITADEL container. (PUT is idempotent.)
	if _, err := api.callMethod(ctx, "PUT", "/v2/features/instance",
		map[string]any{"loginV2": map[string]any{"required": false}}, nil); err != nil {
		return fmt.Errorf("set instance features (login v2 off): %w", err)
	}
	log.Printf("login: using built-in legacy UI (login v2 disabled)")

	// 1. Project, with role assertion so roles ride the token. Idempotent:
	// on re-run the project already exists, so fall back to looking it up.
	projectID, err := ensureProject(ctx, api, "MaagapAruga")
	if err != nil {
		return err
	}
	out.ProjectID = projectID
	out.TelemetryProjectID = projectID
	log.Printf("project: %s", projectID)
	project := struct{ ID string }{ID: projectID}

	// 2. Roles (bulk).
	roleBody := make([]map[string]string, 0, len(roles))
	for _, r := range roles {
		roleBody = append(roleBody, map[string]string{"key": r.key, "displayName": r.name})
	}
	if code, err := api.call(ctx,
		fmt.Sprintf("/management/v1/projects/%s/roles/_bulk", project.ID),
		map[string]any{"roles": roleBody}, nil); err != nil && code != 409 {
		return fmt.Errorf("create roles: %w", err)
	}
	log.Printf("roles: %d ensured", len(roles))

	// 3. Web OIDC app (Auth Code + PKCE, confidential — client id + secret).
	var webApp struct {
		AppID        string `json:"appId"`
		ClientID     string `json:"clientId"`
		ClientSecret string `json:"clientSecret"`
	}
	if code, err := api.call(ctx,
		fmt.Sprintf("/management/v1/projects/%s/apps/oidc", project.ID),
		map[string]any{
			"name":                     "web",
			"redirectUris":             []string{redirect},
			"postLogoutRedirectUris":   []string{postLogout},
			"responseTypes":            []string{"OIDC_RESPONSE_TYPE_CODE"},
			"grantTypes":               []string{"OIDC_GRANT_TYPE_AUTHORIZATION_CODE"},
			"appType":                  "OIDC_APP_TYPE_WEB",
			"authMethodType":           "OIDC_AUTH_METHOD_TYPE_BASIC",
			"accessTokenType":          "OIDC_TOKEN_TYPE_JWT",
			"devMode":                  true, // dev: allow http redirect
			"accessTokenRoleAssertion": true,
			"idTokenRoleAssertion":     true,
			"idTokenUserinfoAssertion": true,
		}, &webApp); err != nil {
		if code != 409 {
			return fmt.Errorf("create web app: %w", err)
		}
		log.Printf("web app already exists; its client secret is only shown at " +
			"creation — delete the 'web' app in ZITADEL and re-run to rotate it")
	} else {
		out.WebClientID = webApp.ClientID
		out.WebClientSecret = webApp.ClientSecret
		log.Printf("web app: client %s", webApp.ClientID)
	}

	// 4. Telemetry service account — the identity mock IoMT devices present.
	//
	// Device tokens are just ZITADEL-signed JWTs; the telemetry service verifies
	// them against the JWKS regardless of HOW they were obtained. So the account
	// is provisioned to support multiple onboarding flows for IoMT research:
	//   - client credentials (M2M): the secret generated here (the default),
	//   - JWT-profile: add a machine key to this same account,
	//   - PAT: mint a personal access token for it.
	// The token's `sub` is this account's user id — the subject OpenFGA
	// authorizes as a `device` on each care recipient — so it is emitted for the
	// tuple sync. The token carries the project audience (out.TelemetryProjectID)
	// via the reserved project-aud scope the device requests.
	telUserID, err := ensureMachineUser(ctx, api, "telemetry-device",
		"Telemetry Device", "Service account for mock IoMT device ingest")
	if err != nil {
		return fmt.Errorf("telemetry service account: %w", err)
	}
	out.TelemetryUserID = telUserID
	log.Printf("telemetry service account: %s", telUserID)

	// Generate M2M client credentials (the default onboarding path). This is
	// not idempotent — each run rotates the secret — so, like the web client
	// secret, it is injected into the cluster at runtime and never committed.
	var telSecret struct {
		ClientID     string `json:"clientId"`
		ClientSecret string `json:"clientSecret"`
	}
	if _, err := api.callMethod(ctx, "PUT",
		fmt.Sprintf("/management/v1/users/%s/secret", telUserID), nil, &telSecret); err != nil {
		return fmt.Errorf("generate telemetry client secret: %w", err)
	}
	out.TelemetryClientID = telSecret.ClientID
	out.TelemetryClientSecret = telSecret.ClientSecret
	log.Printf("telemetry M2M client: %s (secret rotated)", telSecret.ClientID)

	// 5. Mock users + role grants — demonstration seed only.
	if !seedUsers {
		log.Printf("skipping mock users (pass -seed-mock-users for dev/demo); " +
			"a real install creates its admin in the ZITADEL dashboard")

		return emit(out, outPath)
	}

	for _, u := range users {
		var created struct {
			UserID string `json:"userId"`
		}
		if code, err := api.call(ctx, "/management/v1/users/human/_import", map[string]any{
			"userName":               u.email,
			"profile":                map[string]string{"firstName": u.first, "lastName": u.last},
			"email":                  map[string]any{"email": u.email, "isEmailVerified": true},
			"password":               userPassword,
			"passwordChangeRequired": false,
		}, &created); err != nil {
			if code == 409 {
				log.Printf("user %s already exists, skipping", u.email)

				continue
			}

			return fmt.Errorf("create user %s: %w", u.email, err)
		}

		if _, err := api.call(ctx,
			fmt.Sprintf("/management/v1/users/%s/grants", created.UserID),
			map[string]any{"projectId": project.ID, "roleKeys": []string{u.role}}, nil); err != nil {
			return fmt.Errorf("grant %s to %s: %w", u.role, u.email, err)
		}

		log.Printf("user: %s (%s)", u.email, u.role)
	}

	return emit(out, outPath)
}

func emit(out output, outPath string) error {
	encoded, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		return err
	}

	fmt.Println(string(encoded))

	if outPath != "" {
		if err := os.WriteFile(outPath, encoded, 0o600); err != nil {
			return fmt.Errorf("write out file: %w", err)
		}
	}

	return nil
}

func env(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}

	return fallback
}

func envBool(key string, fallback bool) bool {
	switch os.Getenv(key) {
	case "true", "1", "yes":
		return true
	case "false", "0", "no":
		return false
	default:
		return fallback
	}
}
