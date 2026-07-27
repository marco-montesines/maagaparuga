# Installation — local development (minikube)

This guide brings the whole MaagapAruga platform up on your machine: the data layer,
the message broker, the identity stack, the API gateway, and the application services —
all on a single-node [minikube](https://minikube.sigs.k8s.io/) cluster, driven entirely
by `make` targets. This is the **dev** environment (see
[deployment.md](deployment.md) for staging and production on real cloud nodes).

> MaagapAruga is a research and educational software framework, not a medical device,
> and ships only with fictitious mock data. See the root [README](https://github.com/marco-montesines/maagaparuga/blob/master/README.md) and
> [DISCLAIMER](https://github.com/marco-montesines/maagaparuga/blob/master/DISCLAIMER.md).

## Prerequisites

The local bring-up runs prebuilt container images, so you only need a container runtime,
minikube, and the usual Kubernetes CLIs:

| Tool | Why | Notes |
|---|---|---|
| **Docker** | minikube's driver and the image build target | Docker Desktop or an equivalent daemon |
| **minikube** | the local single-node Kubernetes cluster | started automatically by `make dev` |
| **kubectl** | every target talks to the cluster through it | must match your minikube Kubernetes version |
| **make** | the developer entry points live in the [`Makefile`](https://github.com/marco-montesines/maagaparuga/blob/master/Makefile) | GNU make |
| **python3** | used by a couple of targets (`make dev-dns`, proto helpers) | usually already present |

The `make dev` bring-up requests **7 GB of memory and 4 CPUs** for the minikube VM by
default. Override with `MINIKUBE_MEMORY` / `MINIKUBE_CPUS` if needed:

```bash
make dev MINIKUBE_MEMORY=8g MINIKUBE_CPUS=6
```

**Only needed if you rebuild a service image yourself** (the default flow does not):

- **buf** + **Go** — regenerate the gateway's gRPC descriptor set (`make gateway-proto`)
  or build the telemetry image.
- **PHP** / **Python** — only if you change `apps/web` or a `services/*` image and roll
  it with `make web-rebuild` / `make media-rebuild`.

Run `make help` at any time to list every target with its one-line description.

## 1. Bring the platform up

```bash
make dev
```

This starts minikube (if it isn't already running), installs the **CloudNativePG**
operator (the Postgres CRDs), waits for it, then applies the **dev** Kustomize overlay
(`deploy/k8s/overlays/dev`). When it finishes it prints the pod list and the gateway
hint. Give the data-layer pods a moment to become ready:

```bash
make dev-status        # pods, services, PVCs
make dev-wait          # block until every pod is Ready
```

At this point the web and telemetry services run at one replica each, and the data
stores, broker, identity stack (ZITADEL + OpenFGA), and the APISIX gateway are all up —
but identity is **not yet wired** (that is the next step).

## 2. Configure identity (bootstrap)

Two one-time steps make the single-host OIDC issuer resolve the same way for your
browser and for the in-cluster services, then configure ZITADEL and OpenFGA:

```bash
make dev-dns           # adds a CoreDNS rewrite: maagaparuga.test -> the APISIX gateway
```

Add the matching host entry to your machine once (the browser side of the same name):

```
127.0.0.1 maagaparuga.test
```

Then run the bootstrap:

```bash
make dev-bootstrap
```

`dev-bootstrap` runs a ZITADEL bootstrap Job (project, roles, the web OIDC client, the
telemetry service account, and the fictitious login users) and then bootstraps the
OpenFGA store + authorization model, **injecting the store/model ids and client
credentials into the running cluster at runtime** (these values are never committed).
When it completes, the web app can log users in and fine-grained authorization checks
work.

## 3. Load mock data

```bash
make dev-seed
```

This migrates the app database, seeds the fictitious care records and OpenFGA
relationship tuples, and streams a batch of mock vitals into the telemetry service. It
is safe to run against any environment to validate a fresh deployment.

## 4. Verify it's up

```bash
make dev-smoke
```

The smoke test confirms each service answered through its own entry point: the APISIX
`/healthz`, the web app's `/up` (direct and through the gateway), the telemetry ingest +
writer readiness, and the ClickHouse `vitals` row count.

## 5. Open the app

```bash
make dev-gateway       # port-forward APISIX to http://localhost:9080
```

With the `/etc/hosts` entry and the CoreDNS rewrite from step 2 in place, open:

```
http://maagaparuga.test:9080
```

and sign in with a seeded fictitious persona, e.g. `admin@example.com` /
`Password1!`. (On Linux you can also reach the gateway NodePort at
`http://$(minikube ip):30080`; on macOS's docker driver the minikube IP is not
host-routable, so use the port-forward.)

## Reaching other services from your host

ClusterIPs (`10.x.x.x`) are in-cluster-only, so always go through a port-forward:

```bash
make dev-forward SVC=opensearch PORT=9200     # one service
make dev-expose                               # forward every service at once (Ctrl-C stops all)
```

`make dev-expose` prints the full local port map (gateway, PostgreSQL, ClickHouse,
OpenSearch, Redis, SeaweedFS, NATS, ZITADEL, OpenFGA). In-cluster, services address each
other by DNS name (`opensearch:9200`, `nats:4222`, …).

## Optional demos

Each of these exercises a full path end-to-end and prints what it did:

```bash
make dev-simulate SAMPLES=48     # stream mock IoMT device vitals into telemetry
make dev-assessment              # score recipient 1: NEWS2, DASS-21, fuzzy risk -> results + alerts
make dev-media                   # synthesize mock consultations -> transcribe -> index -> hybrid search
```

Turning on the optional auth paths (all off by default in dev, opt-in):

```bash
make dev-device-auth             # telemetry verifies device JWTs + OpenFGA authorizes the device
make dev-media-auth              # media verifies the caller JWT + per-recipient OpenFGA
make dev-assessment-grpc         # switch the assessment vitals reader from ClickHouse to telemetry gRPC
```

See [configuration.md](configuration.md) for what `AUTH_MODE` and these opt-ins change.

## Backups & restore drill (local)

Postgres has continuous backup (WAL + base backups) to the in-cluster SeaweedFS bucket:

```bash
make dev-backup                  # take an on-demand base backup
make dev-restore-verify          # restore drill: recover a throwaway cluster, check row counts, tear down
```

The full strategy is in [deploy/k8s/DISASTER-RECOVERY.md](https://github.com/marco-montesines/maagaparuga/blob/master/deploy/k8s/DISASTER-RECOVERY.md).

## Teardown

```bash
make dev-down                    # remove the stack (keeps minikube + the CNPG operator)
make dev-destroy                 # delete the whole minikube cluster
```

## Troubleshooting

- **Browser login fails / redirects loop** — the OIDC issuer host must resolve the same
  inside and outside the cluster. Re-check step 2 (`make dev-dns` + the `/etc/hosts`
  entry). ZITADEL fixes its external domain at init; if you change the issuer host you
  must re-initialize it with `make dev-reinit-zitadel` (dev only — it wipes ZITADEL's
  database).
- **A store pod is stuck Pending** — usually memory. Give minikube more (see
  `MINIKUBE_MEMORY` above).
- **Verify an overlay builds** without applying it: `make kustomize-check`.
