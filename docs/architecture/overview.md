# Architecture overview

MaagapAruga is a polyglot, Kubernetes-native platform assembled from small
services behind a single API gateway. This page is a map; the reasoning behind
each choice — including the alternatives that were rejected — lives in the
[Architecture Decision Records](../adr/README.md).

> Reminder: this is a **research and educational** framework, **not a medical
> device**. It runs only fictitious mock data. See the
> [Intended use](https://github.com/marco-montesines/maagaparuga/blob/master/README.md#intended-use) section.

## The shape of the system

```
                       ┌──────────────────────────────────────────┐
   browsers / devices  │            APISIX (API gateway)          │
        ────────────►  │   TLS · routing · edge auth · transcode  │
                       └───┬───────────┬──────────────┬───────────┘
                           │           │              │
                    GraphQL BFF     gRPC / REST     REST
                           │           │              │
                    ┌──────▼─────┐ ┌───▼────────┐ ┌───▼──────────┐
                    │  web app   │ │ telemetry  │ │ media /       │
                    │ (Laravel)  │ │   (Go)     │ │ assessment    │
                    └──────┬─────┘ └───┬────────┘ │ (Python)      │
                           │           │          └───┬───────────┘
                           │      NATS JetStream ─────┘   (decouples ingest)
                           │           │
            ┌──────────────┴───────────┴─────────────────────────┐
            │  PostgreSQL · ClickHouse · OpenSearch · Redis ·      │
            │  SeaweedFS   (the right store per workload)          │
            └─────────────────────────────────────────────────────┘

     identity: ZITADEL (OIDC) + OpenFGA (fine-grained authorization)
     observability: OpenTelemetry → Prometheus / Tempo / OpenSearch → Grafana
```

## Components

| Layer | Technology | Notes / ADR |
|---|---|---|
| Gateway | Apache APISIX | Single entry point; TLS, routing, edge auth, gRPC↔REST transcode — [ADR 0003](../adr/0003-apisix-api-gateway.md) |
| Web app + BFF | Laravel + Octane on FrankenPHP, Lighthouse GraphQL | [ADR 0004](../adr/0004-polyglot-services.md), [ADR 0010](../adr/0010-three-api-styles.md) |
| Telemetry ingest | Go, gRPC-first | Device vitals ingest — [ADR 0010](../adr/0010-three-api-styles.md) |
| Assessment | Python / FastAPI | Illustrative scoring (NEWS2, DASS-21, fuzzy risk) |
| Media pipeline | Python / FastAPI + worker | Upload → object store → transcript → embeddings → vector search — [ADR 0008](../adr/0008-media-pipeline.md) |
| Message broker | NATS JetStream | Decouples device ingest — [ADR 0007](../adr/0007-nats-jetstream-message-broker.md) |
| Data stores | PostgreSQL, ClickHouse, OpenSearch, Redis, SeaweedFS | Right store per workload — [ADR 0005](../adr/0005-right-store-per-workload.md), [ADR 0006](../adr/0006-opensearch-as-vector-database.md), [ADR 0015](../adr/0015-seaweedfs-object-storage.md) |
| Identity & authorization | ZITADEL (OIDC) + OpenFGA | [ADR 0009](../adr/0009-zitadel-openfga-identity-authorization.md) |
| Orchestration | Kubernetes everywhere (minikube dev; k3s multi-node clusters) | [ADR 0002](../adr/0002-kubernetes-everywhere.md), [ADR 0014](../adr/0014-microservices-failure-domains.md) |
| Infrastructure as Code | Terragrunt + OpenTofu/Terraform + Ansible | [ADR 0012](../adr/0012-iac-terragrunt-opentofu-ansible.md), [IaC overview](../iac/overview.md) |
| Observability | OpenTelemetry → Prometheus / Tempo / OpenSearch → Grafana unified alerting | [ADR 0011](../adr/0011-observability-stack.md) |
| Backups & DR | PostgreSQL continuous backup + offsite object storage | [ADR 0016](../adr/0016-backup-and-disaster-recovery.md), [DR guide](https://github.com/marco-montesines/maagaparuga/blob/master/deploy/k8s/DISASTER-RECOVERY.md) |

## Three API styles

The platform deliberately uses three complementary API styles, each where it
earns its place ([ADR 0010](../adr/0010-three-api-styles.md)):

- **GraphQL** — the web app's backend-for-frontend, aggregating what a screen needs.
- **gRPC** — telemetry ingest, for compact binary encoding and streaming; APISIX
  transcodes the same service to REST for HTTP clients.
- **REST** — media and assessment services.

See the [integration docs](../integration/README.md) for how to call each one.

## Identity & authorization

Authentication is delegated to **ZITADEL** (OIDC): browsers use the login flow;
devices and services present JWTs. Fine-grained, per-resource authorization is
enforced with **OpenFGA** (e.g. which staff or device may write a given
recipient's vitals). Details in
[ADR 0009](../adr/0009-zitadel-openfga-identity-authorization.md) and the
[IoMT integration guide](../integration/iomt-devices.md).

## Environments

Development runs on a single-node **minikube**; staging and production run on
multi-node **k3s** clusters. See [Deployment](../getting-started/deployment.md)
and the [environments section](https://github.com/marco-montesines/maagaparuga/blob/master/README.md#environments) of the README.
