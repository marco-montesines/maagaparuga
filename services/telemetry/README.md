# services/telemetry — Vitals ingest & read API (Go)

Device-facing biotelemetry: gRPC ingest for (mock) IoMT devices, a windowed read
API for the web BFF and the assessment service, and a mock device fleet.

## Design

- **gRPC-first** (ADR 0010). The contract lives in [`proto/`](../../proto) and is
  linted/generated with [buf](https://buf.build); APISIX's `grpc-transcode`
  plugin exposes the same service as REST, so one implementation serves both.
- **Raw measurements only.** The contract has no field for a device-computed
  clinical score — scores are computed server-side by the assessment service so
  they can be recomputed and audited. A reflection test fails the build if such
  a field is ever added.
- **Ingest never touches the database** (ADR 0007): validate → publish to NATS
  JetStream → return. A separate writer consumes the stream and performs
  **batched** ClickHouse inserts, so a device-fleet burst queues in the broker
  instead of overwhelming the store.
- **Redelivery is safe.** The `vitals` table is a `ReplacingMergeTree` keyed by
  (care recipient, timestamp, device), so an at-least-once replay replaces its
  twin rather than double-counting.
- **Device authentication + authorization** (ADR 0009). *AuthN:* a device
  presents a ZITADEL-signed bearer token, verified locally against the JWKS —
  signature, issuer, audience, expiry — so ingest costs no network round trip
  and survives key rotation. *AuthZ:* every write is then checked against
  **OpenFGA** — the token subject must hold **`vitals_writer`** (= assigned
  staff *or* a provisioned `device`) on that care recipient, and reads require
  `viewer`; a valid token cannot touch a recipient it has no relationship with.
  Health checks are the only exempt methods (probes carry no credentials).
  `AUTH_MODE=disabled` exists for local work and logs a warning on every start.
- **Pluggable device onboarding** ([`internal/devauth`](internal/devauth)). The
  service verifies the JWT the same way however it was obtained, so onboarding
  is a client concern; the simulator supports `-auth-method`:
  `client_credentials` (M2M secret, default), `jwt_profile` (machine key, signed
  assertion), or `static` (a pre-minted token / PAT via `-token`). The token's
  audience is the project id, requested via ZITADEL's reserved project-audience
  scope. In dev, `make dev-device-auth` provisions this and flips the service to
  `AUTH_MODE=jwt`.
- Style: Effective Go + the [Uber Go style guide](https://github.com/uber-go/guide),
  enforced by `.golangci.yml`.

## Roles

One binary, three roles — separately deployable (ADR 0014):

```bash
telemetry serve      # gRPC ingest + windowed read API (port 9090; gRPC health for probes)
telemetry write      # JetStream consumer -> batched ClickHouse inserts (+ /healthz on :9091)
telemetry simulate   # mock IoMT device fleet -> streams into the ingest API
```

Each reads configuration from flags or environment:
- **serve/write:** `NATS_URL`, `CLICKHOUSE_ADDR`, `CLICKHOUSE_DB`,
  `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `OIDC_ISSUER`, `OIDC_AUDIENCE`
  (the project id), `AUTH_MODE`, `OPENFGA_URL`/`OPENFGA_STORE_ID`/
  `OPENFGA_MODEL_ID`; the writer also takes `HEALTH_ADDR` (default `:9091`).
- **simulate:** `DEVICE_AUTH_METHOD`, `OIDC_ISSUER`, `OIDC_AUDIENCE`,
  `DEVICE_CLIENT_ID`/`DEVICE_CLIENT_SECRET` (client_credentials),
  `DEVICE_KEY_PATH` (jwt_profile), or `DEVICE_TOKEN` (static/PAT).

## API surfaces

The same service answers three ways (ADR 0010):

| Surface | Path | Used by |
|---|---|---|
| gRPC streaming | `maagaparuga.telemetry.v1.VitalsService/StreamVitals` | devices holding a long-lived connection |
| REST (transcoded by the gateway) | `POST /v1/vitals`, `POST /v1/vitals/window` | browsers, integrations, curl |
| gRPC unary | `PublishVitals`, `GetWindow` | services (the web BFF reads windows here) |

The gateway transcodes REST↔gRPC from a **compiled descriptor set** generated
from `proto/` (`make gateway-proto`; `make proto-check` fails if it is stale).
Two things to know when calling the REST surface: it uses protobuf's table
mapping rather than canonical protobuf JSON, so timestamps are
`{"seconds":N,"nanos":N}` in both directions, and responses carry a
`"_field":"field"` marker for each present optional field (a presence
indicator, not data).

The gateway enforces auth on these routes: a request without a valid
bearer token is rejected `401` at the edge, before it reaches the service.

```bash
curl -X POST http://<gateway>/v1/vitals \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"sample":{"device_id":"d1","care_recipient_id":"1",
       "measured_at":{"seconds":1784664365,"nanos":0},"heart_rate_bpm":72}}'
```

## Development

```bash
go test ./...                     # table-driven unit tests
go vet ./... && gofmt -l .
golangci-lint run                 # style + correctness gate
(cd ../../proto && buf lint && buf generate)   # regenerate after contract changes
```

The mock fleet models single-purpose devices (pulse oximeter, thermometer,
blood-pressure monitor, respiration band) whose baselines drift as bounded
random walks, so a window of samples looks like a person rather than noise.
`simulate -burst` floods the ingest path to demonstrate broker buffering.
