# Architecture Decision Records

> Pre-release: these are living decisions. **Dates are stamped at the public release**,
> not while the repository is private — so a superseded ADR shows the evolution without
> pinning a misleading timeline.


Every significant architectural choice in MaagapAruga is recorded here as an ADR:
the context, the **options considered — including the ones rejected and why**, the
decision, and its consequences (including the conditions under which the decision
should be revisited).

The point is stated in the main README: *an architecture is a set of decisions with
reasons, and reasons get re-evaluated when the requirements change.* ADRs make those
reasons inspectable.

| # | Decision | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions as ADRs | Accepted |
| [0002](0002-kubernetes-everywhere.md) | Kubernetes in every environment (minikube / k3s) | Accepted |
| [0003](0003-apisix-api-gateway.md) | Apache APISIX as the API gateway | Accepted |
| [0004](0004-polyglot-services.md) | Polyglot services — Go, Python, PHP (Laravel + Octane on FrankenPHP) | Accepted |
| [0005](0005-right-store-per-workload.md) | Right store per workload — PostgreSQL, ClickHouse, OpenSearch, Redis, MinIO | Accepted |
| [0006](0006-opensearch-as-vector-database.md) | OpenSearch as the vector database (no dedicated vector store) | Accepted |
| [0007](0007-nats-jetstream-message-broker.md) | NATS JetStream as the message broker (not Kafka, not Redpanda) | Accepted |
| [0008](0008-media-pipeline.md) | Media pipeline — faster-whisper speech-to-text, app-side embeddings | Accepted |
| [0009](0009-zitadel-openfga-identity-authorization.md) | ZITADEL (OIDC) + OpenFGA for identity and authorization | Accepted |
| [0010](0010-three-api-styles.md) | Three API styles — REST, gRPC, GraphQL, each where justified | Accepted |
| [0011](0011-observability-stack.md) | Observability — OpenTelemetry → Prometheus/Tempo/OpenSearch → Grafana | Accepted |
| [0012](0012-iac-terragrunt-opentofu-ansible.md) | IaC — Terragrunt + OpenTofu/Terraform + Ansible on Hetzner Cloud | Accepted |
| [0013](0013-latest-stable-pinned-versions.md) | Latest stable releases, pinned exactly | Accepted |
| [0014](0014-microservices-failure-domains.md) | Microservices, not a monolith; failure domains stated honestly | Accepted |
| [0015](0015-seaweedfs-object-storage.md) | SeaweedFS replaces MinIO as the object store (upstream discontinued) | Accepted |

Format: lightweight [MADR](https://adr.github.io/madr/)-style. New decisions get new
numbers; superseded ADRs are never deleted — their status changes and they link forward.
