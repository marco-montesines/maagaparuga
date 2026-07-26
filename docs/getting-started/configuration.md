# Configuration

How the platform is configured across environments: the base domain, per-service
settings, the identity/authorization wiring, and where secrets come from. The guiding
rule is **the same manifests run everywhere — only overlay variables differ**
([ADR 0002](../adr/README.md)).

## Configuration layers

Configuration lives in three places, from most general to most specific:

| Layer | What it holds | Where |
|---|---|---|
| **Kustomize base** | every component, single-node defaults, exact image pins, the per-service `ConfigMap`s | `deploy/k8s/base/**` |
| **Overlay** | the per-environment differences (issuer host, auth mode, replicas, HA patches) | `deploy/k8s/overlays/{dev,staging,production}` |
| **Runtime injection** | per-install values that are never committed (client secrets, OpenFGA store/model ids, tokens) | patched into `Secret`s / `ConfigMap`s at bootstrap time |

Nothing sensitive is committed. See [Secrets](#where-secrets-come-from) below.

## The base domain is a variable

There is **no hard-coded TLD anywhere** — the platform serves under one base domain you
choose:

- **dev** uses the local host `maagaparuga.test`, mapped to the gateway by a CoreDNS
  rewrite (`make dev-dns`) plus a matching `/etc/hosts` entry. The web app's issuer is
  set by `ZITADEL_BASE_URL=http://maagaparuga.test:9080` in the dev overlay.
- **staging / production** take the hostname from the Terragrunt `domain` input
  (`infra/terragrunt/<env>/terragrunt.hcl`) and the production overlay points the
  services at it (`https://<domain>`). The repository's own environments use DuckDNS
  hostnames (`maagaparuga.duckdns.org`, `staging-maagaparuga.duckdns.org`), but the name
  is entirely yours to set.

The OIDC issuer is deliberately a **single host** shared by ZITADEL and the web app, so
it must resolve identically for the browser and for in-cluster services — that is why
both dev and the cloud overlays add a CoreDNS rewrite to the gateway/TLS edge.

## Per-service configuration

Each application service reads a `ConfigMap` (defined in `deploy/k8s/base/apps/apps.yaml`)
plus a `Secret` for credentials. The keys that matter most:

### `web-config` (Laravel / FrankenPHP web app)

| Key | Default (base) | Purpose |
|---|---|---|
| `ZITADEL_BASE_URL` | `http://zitadel:8080` | OIDC issuer base — overlays point this at the shared issuer host |
| `OPENFGA_URL` | `http://openfga:8080` | OpenFGA API endpoint for fine-grained checks |

Secret `web-secrets` carries `APP_KEY`, the `ZITADEL_CLIENT_*` values, and the
`OPENFGA_STORE_ID` / `OPENFGA_MODEL_ID` — the last four are **filled by the bootstrap**,
empty until then (empty means authorization fails closed).

### `telemetry-config` (Go vitals ingest + read API)

| Key | Default (base) | Purpose |
|---|---|---|
| `NATS_URL` | `nats://nats:4222` | broker for vitals events |
| `CLICKHOUSE_ADDR` / `CLICKHOUSE_DB` / `CLICKHOUSE_USER` | `clickhouse:9000` / `maagaparuga` | vitals time-series store |
| `OIDC_ISSUER` | issuer host | where device JWTs are verified (JWKS) |
| `OIDC_AUDIENCE` | (injected) | the ZITADEL project id a device token must carry |
| `AUTH_MODE` | `disabled` in **dev**, `jwt` in cloud | device authentication + per-recipient authorization |
| `OPENFGA_STORE_ID` / `OPENFGA_MODEL_ID` | (injected) | needed once `AUTH_MODE=jwt` |

### `assessment-config` (Python scoring service)

| Key | Default | Purpose |
|---|---|---|
| `VITALS_READER` | `clickhouse` | vitals source: `clickhouse` (default) or `grpc` (read via the telemetry gRPC API) |
| `CLICKHOUSE_HOST` / `CLICKHOUSE_PORT` / `CLICKHOUSE_DB` | `clickhouse` / `8123` / `maagaparuga` | direct-read path |

When `VITALS_READER=grpc`, `TELEMETRY_GRPC` + a `TELEMETRY_TOKEN` bearer are injected at
runtime (`make dev-assessment-grpc`), and the service reads with a least-privilege
OpenFGA `service_reader` grant.

### `media-config` (Python media pipeline)

| Key | Default | Purpose |
|---|---|---|
| `S3_ENDPOINT` / `S3_BUCKET` / `S3_REGION` | `http://seaweedfs:8333` / `media` / `us-east-1` | object store for media originals |
| `NATS_URL` | `nats://nats:4222` | processing-job queue |
| `AUTH_MODE` | `disabled` in **dev**, `jwt` in cloud | caller-JWT verification + per-recipient OpenFGA |
| `OIDC_ISSUER` | issuer host | JWKS source when `AUTH_MODE=jwt` |
| `OPENFGA_API_URL` | `http://openfga:8080` | authorization checks (reads need `viewer`, writes `editor`) |

The `S3_ENDPOINT` is the only thing tying the media service to SeaweedFS — pointing it at
any S3-compatible endpoint (with matching credentials) is all it takes to swap the object
store.

## Authentication and authorization

Two systems, both keeping state in PostgreSQL:

- **ZITADEL (OIDC + PKCE)** handles login and issues tokens. The **issuer is a single
  host** (see above). Browser login flows through the Laravel app via Socialite; device
  and machine-to-machine clients use the standard Authorization Code + PKCE or
  client-credentials flows.
- **OpenFGA (relationship-based)** answers "may caregiver A see care recipient B?" The
  **store id and model id are created by the bootstrap** (`php artisan fga:bootstrap`)
  and injected into the services — they are per-install values, never committed.

### `AUTH_MODE` and the opt-in auth paths

The device (telemetry) and media services ship with `AUTH_MODE=disabled` **in dev** so a
plain `make dev` comes up without identity wiring (each service warns loudly on every
start while disabled). You turn each on explicitly:

| Target | What it does |
|---|---|
| `make dev-bootstrap` | prerequisite — provisions the ZITADEL clients/service accounts + OpenFGA store/model |
| `make dev-device-auth` | injects the device credential, grants the device `vitals_writer` in OpenFGA, flips telemetry to `AUTH_MODE=jwt` |
| `make dev-media-auth` | grants a caller `assigned_staff` on mock recipients, flips media to `AUTH_MODE=jwt` |
| `make dev-assessment-grpc` | grants the assessment service a read-only `service_reader`, switches `VITALS_READER=grpc` |

In the cloud overlays these are not optional: the production overlay's
`patches/auth-and-issuer.yaml` sets `AUTH_MODE=jwt` for both telemetry and media and
points `OIDC_ISSUER` at the real HTTPS issuer. The per-install `OIDC_AUDIENCE` and the
OpenFGA store/model ids are still injected at deploy time (the same values the dev
targets inject).

## Where secrets come from

Secret handling differs by environment on purpose:

| Environment | Secrets | Rationale |
|---|---|---|
| **dev** | well-known throwaway literals generated by the dev overlay's `secretGenerator` | a local, disposable cluster holding only mock data — these are not real secrets |
| **staging** | throwaway literals, also from a `secretGenerator` | staging is ephemeral and holds only synthetic mock data; the values just satisfy each component's need for *a* credential so it boots |
| **production** | **provisioned out-of-band at deploy time** — nothing sensitive is committed | real, per-install credentials |

`kubectl kustomize` builds the production overlay with **no secrets**; the pods stay
pending until you create them (from gitignored `secrets/*.env`, a `kubectl create secret`
script, or SealedSecrets). The full list of secrets to provision is the table in
[`deploy/k8s/overlays/production/README.md`](https://github.com/marco-montesines/maagaparuga/blob/master/deploy/k8s/overlays/production/README.md)
— it covers the database credentials, `openfga-datastore`, ClickHouse / OpenSearch /
Redis credentials, `seaweedfs-s3-config`, the `zitadel-masterkey` (exactly 32 bytes),
`web-secrets`, `telemetry-secrets`, `media-s3`, `grafana-admin`, the **`pg-backup-s3`**
offsite backup key (Backblaze B2), and the **`ghcr-pull`** image-pull secret for the
container registry.

Runtime-injected values (`OPENFGA_STORE_ID`, `OPENFGA_MODEL_ID`, `ZITADEL_CLIENT_*`,
`DEVICE_CLIENT_*`, gRPC tokens) are filled by the bootstrap step after apply, exactly as
the dev `make` targets do locally — see [deployment.md](deployment.md).

## Infrastructure configuration (cloud)

The cloud environments are parameterized by Terragrunt inputs
(`infra/terragrunt/<env>/terragrunt.hcl`): `environment`, `node_count` (default 3),
`server_type`, `location`, the private-network `ip_range` / `subnet_range`, and `domain`.
Sensitive inputs (`hcloud_token`, `admin_allowed_ips`, `ssh_key_names`) come from a
gitignored `secrets.auto.tfvars` (see the `*.tfvars.example`) or environment variables.
Ansible selects which Kubernetes overlay to apply via `-e env=<name>`. Details in
[deployment.md](deployment.md).
