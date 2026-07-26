# Integrating an IoMT device

The end-to-end walkthrough for connecting a (mock) IoMT device to the telemetry
service: obtain a token, get authorized for a care recipient, and stream vitals.
Every claim here is grounded in the telemetry service code
(`services/telemetry/internal/{devauth,auth,authz,server}`).

> **Research/educational framework — not a medical device.** Use only fictitious
> mock devices and mock care-recipient IDs (this guide uses `1`–`4`). Never send
> real personal or health data. See [`DISCLAIMER.md`](https://github.com/marco-montesines/maagaparuga/blob/master/DISCLAIMER.md).

## The shape of the integration

A device does four things:

1. **Obtain a bearer token** from ZITADEL (one of three onboarding modes).
2. **Be authorized** as a `vitals_writer` for the care recipient(s) it reports
   on (an OpenFGA relationship, provisioned by an operator).
3. **Send vitals** — raw measurements only — either by streaming gRPC
   (`StreamVitals`) or one sample at a time (`PublishVitals` / REST `/v1/vitals`).
4. Repeat: mint a fresh short-lived token as needed and keep streaming.

The telemetry service verifies only that the token is a valid ZITADEL-signed JWT
with the right issuer and audience — it does **not** care *how* the device
obtained it. That is the seam the onboarding modes plug into.

## 1. Obtain a ZITADEL token

`services/telemetry/internal/devauth` offers three onboarding methods behind one
interface. All three yield the same thing: a short-lived access token whose
audience is the MaagapAruga project, requested via ZITADEL's reserved
project-audience scope (`urn:zitadel:iam:org:project:id:<projectID>:aud`) so the
token validates at the telemetry service.

| Method | Device holds | Grant | When to use |
|---|---|---|---|
| `client_credentials` *(default)* | a client id + secret | OAuth2 `client_credentials` | provisioned M2M devices |
| `jwt_profile` | a private key (ZITADEL machine-key JSON) | `urn:ietf:params:oauth:grant-type:jwt-bearer` | no secret crosses the wire; device signs an assertion |
| `static` | a pre-minted bearer token (e.g. a ZITADEL PAT) | none at runtime | simplest onboarding / testing |

### `client_credentials` (default)

The standard machine-to-machine flow. The device presents its client id +
secret (HTTP Basic) to ZITADEL's token endpoint and receives an access token:

```bash
curl -s -u "$DEVICE_CLIENT_ID:$DEVICE_CLIENT_SECRET" \
  -d grant_type=client_credentials \
  -d "scope=openid urn:zitadel:iam:org:project:id:$PROJECT_ID:aud" \
  "$OIDC_ISSUER/oauth/v2/token"
```

The `access_token` field of the JSON response is the bearer for telemetry.

### `jwt_profile`

The device holds a ZITADEL machine-key JSON file (`keyId`, `key` PEM, `userId`).
It signs a short-lived JWT assertion (RS256) addressed to the issuer and
exchanges it — no secret on the wire, the device proves possession of the key:

```bash
# assertion = a device-signed JWT (iss=sub=userId, aud=issuer, exp≈now+1h)
curl -s \
  -d grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer \
  -d "assertion=$ASSERTION" \
  -d "scope=openid urn:zitadel:iam:org:project:id:$PROJECT_ID:aud" \
  "$OIDC_ISSUER/oauth/v2/token"
```

### `static`

A pre-minted token supplied out of band (a ZITADEL personal access token, or any
bearer token). No runtime exchange happens — the device just presents it.

### Doing it with the built-in client

The telemetry binary's `simulate` command mints the token for you per the
selected method — a working reference for your own device firmware:

```bash
# client_credentials (default)
telemetry simulate \
  -oidc-issuer "$OIDC_ISSUER" \
  -client-id "$DEVICE_CLIENT_ID" \
  -client-secret "$DEVICE_CLIENT_SECRET" \
  -audience "$PROJECT_ID" \
  -recipients 1,2 -devices 2

# jwt_profile
telemetry simulate -auth-method jwt_profile \
  -oidc-issuer "$OIDC_ISSUER" -key ./device-machine-key.json -audience "$PROJECT_ID"

# static / PAT (overrides -auth-method)
telemetry simulate -token "$DEVICE_TOKEN"
```

Equivalent environment variables: `DEVICE_AUTH_METHOD`, `OIDC_ISSUER`,
`DEVICE_CLIENT_ID`, `DEVICE_CLIENT_SECRET`, `OIDC_AUDIENCE`, `DEVICE_KEY_PATH`,
`DEVICE_TOKEN`, `TELEMETRY_TARGET`.

## 2. What the token must satisfy

The telemetry service (`internal/auth`) verifies each token's **signature**
against ZITADEL's JWKS (cached, survives key rotation), then checks the claims:

- **`iss`** must equal the configured issuer.
- **`aud`** must contain the service's configured audience (the project id) —
  this is why the token is requested with the project-audience scope. A token
  minted for another service is rejected even if the signature is valid.
- **`exp`** must be in the future.

The credential is presented as a gRPC `authorization` metadata header (or an
`Authorization: Bearer <token>` header on the REST surface). No token, malformed
token, or failed verification → `Unauthenticated`.

## 3. Be authorized for the care recipient (OpenFGA)

Authentication proves the token is real; it does **not** decide *which* care
recipients the device may write. That is a per-recipient **OpenFGA** check
(`internal/authz`), the same relationship model the web app enforces
([ADR 0009](../adr/0009-zitadel-openfga-identity-authorization.md)):

- Vitals ingest (`StreamVitals`, `PublishVitals`) requires the caller (the
  token's `sub`) to hold **`vitals_writer`** on `care_recipient:<id>`.
  `vitals_writer` is the device-or-assigned-staff relation.
- The windowed read (`GetWindow`) requires **`viewer`**.

An operator provisions the relationship as an OpenFGA tuple, e.g. conceptually
`user:<device-subject>  vitals_writer  care_recipient:1`. Without it, a device
with a perfectly valid token is refused (`PermissionDenied`) — this is what
stops one device from writing another recipient's data (the object-level access
flaw the check exists to prevent). Any check error — including a transport or
config failure — is treated as a denial; the service never fails open.

## 4. Send vitals — raw measurements only

Devices send raw measurements; the platform computes any score server-side.
Samples must pass validation (required identifiers + timestamp + at least one
in-range measurement — see [telemetry-grpc.md](telemetry-grpc.md#validation)).

### Streaming (preferred for a fleet) — `StreamVitals`

Client-streaming: one connection, continuous push, one summary reply at the end.
Accepted samples are published to the broker; invalid ones are counted and
dropped without breaking the stream. Authorization is checked the first time each
care recipient appears and cached for the rest of the stream. Generate gRPC stubs
from `proto/maagaparuga/telemetry/v1/vitals.proto`; the in-repo simulator is a
full worked client.

### One sample over gRPC — `PublishVitals`

```bash
grpcurl \
  -H "authorization: Bearer $TOKEN" \
  -d '{
        "sample": {
          "device_id": "mock-oximeter-01",
          "care_recipient_id": "1",
          "measured_at": "2026-07-25T12:00:00Z",
          "heart_rate_bpm": 72,
          "spo2_percent": 97.4
        }
      }' \
  <gateway-host>:443 maagaparuga.telemetry.v1.VitalsService/PublishVitals
```

Response: `{"accepted": "1"}`.

### One sample over REST — `/v1/vitals`

For clients that can't speak gRPC, the gateway transcodes `PublishVitals` to
REST. Note the timestamp is `{"seconds": N, "nanos": N}`, not RFC3339 (a
transcoding quirk — see [telemetry-grpc.md](telemetry-grpc.md#rest-transcoded-equivalents)):

```bash
curl -X POST https://<gateway-host>/v1/vitals \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "sample": {
          "device_id": "mock-oximeter-01",
          "care_recipient_id": "1",
          "measured_at": {"seconds": 1785326400, "nanos": 0},
          "heart_rate_bpm": 72,
          "spo2_percent": 97.4
        }
      }'
```

## Dev vs. enforced auth

The telemetry service has an `AUTH_MODE` switch:

- **`AUTH_MODE=jwt`** — verifies the device JWT **and** enforces the per-recipient
  OpenFGA check. This is how cloud deployments run. `main.go` defaults to `jwt`.
- **`AUTH_MODE=disabled`** — skips both, for local development only. The service
  logs a loud warning at startup and accepts tokenless streams. Local `make`
  demo targets run in this mode; the simulator streams without a token when no
  credentials are configured.

When you disable authentication you also disable per-object authorization (there
is no caller identity to authorize against) — the two move together by design.

## Edge behaviour at the gateway

- **REST routes** (`/v1/vitals`, `/v1/vitals/window`) are edge-authenticated:
  anonymous/invalid bearer → `401` at the gateway; a valid bearer is forwarded
  and re-checked by the service.
- **Native gRPC streaming** (`/maagaparuga.telemetry.v1.VitalsService/*`) is
  **not** edge-authenticated today — the gateway's OIDC plugin does not reject
  unauthenticated client-streaming gRPC. That path is instead gated at the
  service: telemetry verifies the JWT + OpenFGA on every stream. So the device's
  credential is always required; it is simply enforced at the service for
  streaming and at the edge for REST.
