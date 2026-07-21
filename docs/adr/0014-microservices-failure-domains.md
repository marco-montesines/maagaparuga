# 0014 — Microservices, not a monolith; failure domains stated honestly

Date: 2026-07-20 · Status: **Accepted**

## Context

Two properties must not be confused:

1. **Architectural style** — is this a monolith or microservices?
2. **Failure domain** — what fails together when hardware fails?

A monorepo on a single VM can be mistaken for a monolithic platform. It is not — but
the single VM *is* a shared failure domain, and pretending otherwise would be
dishonest.

## Options considered

- **A monolithic application** — one codebase, one process, one database. Rejected:
  the workloads (product CRUD, streaming ingest, scientific scoring, media ML) have
  different languages, scaling shapes, and failure modes; a monolith couples all of
  them.
- **Microservices spread across many VMs from day one** — the "real" HA topology.
  Rejected *as the default* on cost grounds: multiplying VMs multiplies monthly cost
  for a demonstration platform (FinOps is a first-class constraint).
- **Microservices architecture on a single-node deployment, with the HA path built
  in** ✅.

## Decision

The platform is **microservices by construction**, monorepo notwithstanding:

- Each service (web, telemetry API, telemetry writer, assessment, media intake, media
  worker) is an independently built, deployed, and scaled container with its own
  codebase, test lane, and contract (REST/protobuf/GraphQL).
- Services share **no code and no in-process calls** — they communicate only through
  APIs and the message broker; ingest is decoupled from processing by durable streams
  (ADR 0007).
- Services are **stateless**; all state lives in the stores (ADR 0005). Any service
  scales by replica count alone.

**No *architectural* single point of failure:** every component is either replicable
(stateless services, gateway) or clusterable (PostgreSQL primary+replica with automated
failover via CloudNativePG; ClickHouse 3-node; OpenSearch 3-node; NATS clustering;
SeaweedFS replication; Redis replica). The cluster overlay demonstrates exactly this
shape.

**One honest exception at demonstration scale:** each environment runs on a single VM,
so the *infrastructure* failure domain is that VM. This is a deliberate, documented
cost trade-off — not an architectural property. Within the node, Kubernetes provides
self-healing (restarts, probes, resource isolation); JetStream persistence survives pod
restarts.

**Removing the infrastructure SPOF is a topology change, not a redesign:** multi-node
k3s (or any Kubernetes) across ≥3 VMs plus a load balancer, the cluster overlay's node
counts turned up, and replicas >1 for the stateless services. No service code changes.

## Consequences

- The platform can be honestly described as microservices; it must **never** be
  described as highly available at demonstration scale — availability claims follow
  the deployed topology, not the architecture diagram.
- The HA topology is a first-class documented path (cluster overlay + IaC node-count
  variables), kept continuously deployable.
- **Clustering only counts on separate machines.** Replicas colocated on one VM share
  the same disk IO, memory bandwidth, CPUs, *and* failure domain — the bottleneck
  resources — so a single-host "cluster" demonstrates topology, never capacity or
  availability. The production cluster shape is one VM per data node (multi-node
  Kubernetes over a private network) with **pod anti-affinity** so no two replicas of
  the same store share a host; VM count and node count are the same IaC variable.
- Revisit when: any real availability requirement appears — the first step is 3 VMs +
  load balancer, and every decision above already anticipates it.
