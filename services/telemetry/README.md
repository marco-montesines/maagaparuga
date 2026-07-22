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
- **Device authentication** (ADR 0009): bearer tokens are verified locally
  against the identity provider's JWKS — signature, issuer, audience and
  expiry — so ingest costs no network round trip per call and survives key
  rotation. Health checks are the only exempt methods (probes carry no
  credentials). `AUTH_MODE=disabled` exists for local work and logs a warning
  on every start.
- Style: Effective Go + the [Uber Go style guide](https://github.com/uber-go/guide),
  enforced by `.golangci.yml`.

## Roles

One binary, three roles — separately deployable (ADR 0014):

```bash
telemetry serve      # gRPC ingest + windowed read API (port 9090)
telemetry write      # JetStream consumer -> batched ClickHouse inserts
telemetry simulate   # mock IoMT device fleet -> streams into the ingest API
```

Each reads configuration from flags or environment (`NATS_URL`,
`CLICKHOUSE_ADDR`, `CLICKHOUSE_DB`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`,
`OIDC_ISSUER`, `OIDC_AUDIENCE`, `AUTH_MODE`; the simulator takes
`DEVICE_TOKEN`).

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

```bash
curl -X POST http://<gateway>/v1/vitals -H 'Content-Type: application/json' \
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
