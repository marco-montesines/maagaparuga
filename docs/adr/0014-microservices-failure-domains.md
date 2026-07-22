# 0014 — Microservices, not a monolith; failure domains stated honestly

Status: **Accepted**

## Context

Two properties must not be confused:

1. **Architectural style** — is this a monolith or microservices?
2. **Failure domain** — what fails together when hardware fails?

A monorepo can be mistaken for a monolithic platform. It is not — but *where the
services run* is a separate question from *how they are built*, and the two must not be
conflated. Getting the failure-domain answer right is what drove production to a
multi-node cluster rather than a single box.

## Options considered

- **A monolithic application** — one codebase, one process, one database. Rejected:
  the workloads (product CRUD, streaming ingest, scientific scoring, media ML) have
  different languages, scaling shapes, and failure modes; a monolith couples all of
  them.
- **Many-node / one-VM-per-data-node from day one** — maximum isolation, but ~8–10 VMs
  for the store clusters alone. Rejected as overkill for a single-region deployment: the
  cost multiplies for isolation this scale never exercises.
- **Single-node everywhere** — cheapest, but leaves production with an infrastructure
  single point of failure, which contradicts the no-SPOF goal for an environment meant
  to be stable. Rejected for production; kept only for local dev.
- **3-node HA cluster for production, mirrored by staging, single-node dev** ✅ — real
  fault tolerance at a sane, bounded cost.

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
SeaweedFS replication; Redis replica).

**Production deploys that shape as a 3-node cluster.** k3s across three VMs on a private
network; stateless services run replicas>1 spread by **pod anti-affinity**; the store
clusters get real 3-way quorum with no two replicas of a store on the same host. Losing
a node degrades the platform but does not take it down — there is no single-VM point of
failure.

**Staging mirrors production exactly** (same 3-node shape, same manifests) because it is
a *deploy rehearsal*: a single-node staging could not exercise anti-affinity placement,
cross-node networking, quorum, or multi-node rolling updates, so it would not rehearse
what production actually does. Staging stays inexpensive through **ephemerality, not
shrinkage** — created for the rehearsal, destroyed after, billed hourly.

**Local dev is the one single-node environment** (minikube), and correctly so: it
develops code, it does not rehearse a deploy, and there is nothing to protect. The
multi-node cluster shape is available on minikube's multi-node mode when the clustered
behaviour itself needs exercising locally.

## Consequences

- Production can be honestly described as highly available (no single-VM SPOF);
  availability claims still follow the deployed topology, so *dev* is never described
  as HA.
- **Clustering only counts on separate machines.** Replicas colocated on one VM share
  the same disk IO, memory bandwidth, CPUs, *and* failure domain — the bottleneck
  resources — so one-host "clustering" buys topology, never capacity or availability.
  Hence one VM per cluster node, with **pod anti-affinity**; VM count and store
  node-count are the same IaC variable, and cost-guard budgets scale with it.
- Scaling beyond 3 nodes is a change of node count, not a redesign — no service code
  changes.
- Revisit when: load outgrows a 3-node quorum (shard, add nodes) or a stricter
  availability target appears (multi-region, which is a larger change).
