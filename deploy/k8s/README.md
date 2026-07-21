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
  apisix/              #   API gateway (standalone mode; full routes land in P5)
  apps/                #   app-service shells (images built in P2-P4)
overlays/
  dev/                 # minikube: dev-only creds, apps scaled to 0, NodePort 30080
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
- **App services** are scaled to 0 in dev until their images exist — flip each to 1 as
  its phase lands (web -> P2, telemetry -> P3, assessment -> P4, media -> P4b).
- **Cluster shape**: node counts are variables; a `cluster` overlay (P6) demonstrates
  OpenSearch x3, ClickHouse x3 + Keeper, PostgreSQL primary + replica (ADR 0014).
- Every workload declares resource requests and limits (FinOps: right-sizing on small
  VMs).
