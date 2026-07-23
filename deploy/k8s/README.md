# deploy/k8s — Kubernetes manifests

Kustomize **base + overlays** (ADR 0002): the same manifests run everywhere, only
overlay variables differ.

```
base/                  # every component, single-node defaults, exact image pins
  postgres/            #   PostgreSQL via CloudNativePG (+ zitadel/openfga DBs)
  clickhouse/          #   vitals time-series
  opensearch/          #   search + logs + vector DB (3.x)
  redis/               #   sessions/cache
  seaweedfs/           #   S3 data lake (+ bucket bootstrap job; ADR 0015)
  nats/                #   JetStream message broker
  zitadel/             #   OIDC identity provider
  openfga/             #   fine-grained authorization
  apisix/              #   API gateway (standalone; routes + P5 edge auth, TLS/rate-limit TODO)
  observability/       #   Prometheus + Grafana (unified alerting; backup-failure alert)
  apps/                #   app-service shells (images built in P2-P4)
overlays/
  dev/                 # minikube: dev-only creds; web + telemetry live, assessment/media at 0
  staging/             # k3s on the staging VM (P6)
  production/          # k3s on the production VM (P6)
```

## Usage

```bash
make dev          # minikube start + CNPG operator + apply overlays/dev
make dev-status   # pods/services/PVCs
make dev-down     # remove the stack
```

The gateway is the single entry point — `make dev-gateway` then `http://localhost:9080`.

**Reaching services from the host:** ClusterIPs (`10.x.x.x`) are virtual, in-cluster-only
addresses — they are never reachable from your machine, and on macOS's docker driver the
minikube node IP (NodePorts) isn't host-routable either. Always use a port-forward:
`make dev-forward SVC=opensearch PORT=9200` → `http://localhost:9200`. In-cluster,
services address each other by DNS name (`opensearch:9200`, `nats:4222`, …).

## Conventions

- **Versions** (ADR 0013): manifests use the tag `pinned`; the exact versions live in
  `base/kustomization.yaml` (`images:`) — one place to bump, automated updates keep
  them current. (Exception: the CNPG `Cluster.spec.imageName`, pinned in place — it is
  a CR field the image transformer cannot reach.)
- **Secrets**: the dev overlay generates **dev-only, well-known credentials** for a
  throwaway local cluster — they are not secrets. Cloud overlays receive real secret
  provisioning in P6; nothing secret is ever committed (see `.gitignore`).
- **App services** activate as their phase lands: **web (P2)** and **telemetry +
  telemetry-writer (P3)** run at replicas 1; **assessment (P4)** and **media (P4b)**
  stay scaled to 0 until their images exist.
- **Cluster shape**: node counts are variables; a `cluster` overlay (P6) demonstrates
  OpenSearch x3, ClickHouse x3 + Keeper, PostgreSQL primary + replica (ADR 0014).
- Every workload declares resource requests and limits (FinOps: right-sizing on small
  VMs).


## Browser login (dev)

The OIDC issuer is a single host shared by ZITADEL and the web app, so it must
resolve the same for your browser and inside the cluster:

1. `make dev-dns` — adds a CoreDNS rewrite so the cluster resolves
   `maagaparuga.test` to the gateway.
2. Add to your `/etc/hosts` once:  `127.0.0.1 maagaparuga.test`
3. `make dev-bootstrap` — configures ZITADEL (project, roles, web OIDC client,
   telemetry service account) and OpenFGA; injects the client id/secret at
   runtime (never committed).
4. `make dev-gateway`, then open `http://maagaparuga.test:9080` and sign in
   (dev personas: `admin@example.com` / `Password1!`).

## Device (IoMT) auth (dev)

The telemetry service starts with `AUTH_MODE=disabled` so `make dev` comes up
without identity wiring (it warns loudly on every start). To turn on device
authentication + per-recipient authorization:

1. `make dev-bootstrap` — provisions the telemetry device service account and
   emits its M2M credentials.
2. `make dev-device-auth` — injects the device credential (runtime-only, never
   committed), authorizes the device in OpenFGA (the `device` relation on the
   mock recipients), and flips telemetry to `AUTH_MODE=jwt`.
3. `make dev-simulate` — streams mock vitals as an **authenticated** device.

How it works: the device obtains a ZITADEL-signed JWT (audience = the project
id); telemetry verifies it against the JWKS, then OpenFGA checks the token
subject holds `vitals_writer` (= `assigned_staff or device`) on the care
recipient. A tokenless stream is rejected `Unauthenticated`; a stream for a
recipient the device isn't granted is rejected `PermissionDenied`. Onboarding
method is pluggable (`-auth-method`): `client_credentials` (default),
`jwt_profile` (machine key), or `static` (a pre-minted token via `-token`).

## Backups & disaster recovery

Postgres has continuous backup (WAL archiving + base backups) to S3 — in dev,
the in-cluster SeaweedFS `pg-backups` bucket. See **[DISASTER-RECOVERY.md](
DISASTER-RECOVERY.md)** for the full strategy (per-data-class tooling,
ransomware controls, RPO/RTO).

- `make dev-backup` — take an on-demand base backup.
- `make dev-restore-verify` — restore drill: recover a throwaway cluster from
  the backup, confirm row counts match, tear it down.

A **backup-failure alert** is wired (Grafana unified alerting, provisioned as
code in `base/observability/`): Prometheus scrapes CNPG's backup metrics and
Grafana fires `PostgresBackupFailed` when the last backup attempt failed
(recovery point not advancing), auto-resolving when a good backup lands.
Reach Grafana with `make dev-forward SVC=grafana PORT=3000` (admin /
`dev-grafana-admin` in dev).
