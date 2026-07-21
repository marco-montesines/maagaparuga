# 0005 — Right store per workload

Date: 2026-07-20 · Status: **Accepted** — object-store selection superseded by [ADR 0015](0015-seaweedfs-object-storage.md)

## Context

The platform has five distinct data workloads: transactional records, high-volume
time-series, text/semantic search + logs, ephemeral session/cache state, and large
binary objects. One database cannot serve all five well; ten databases cannot fit on
one VM.

## Options considered

- **PostgreSQL for everything** — fewest moving parts; rejected: time-series volume,
  log search, and vector search are all served notably better by purpose-built engines,
  and demonstrating store selection is a goal of the platform.
- **One store per workload, each with exactly one job** ✅:
  - **PostgreSQL** (via the CloudNativePG operator) — system of record; also hosts
    identity (ZITADEL) and authorization (OpenFGA) state. 1 instance by default,
    primary + streaming replica demonstrated.
  - **ClickHouse** — vitals time-series/analytics; 1 node by default, 3-node cluster
    (+ 3× Keeper) demonstrated.
  - **OpenSearch** — full-text + vector search and centralized logs (see ADR 0006);
    1 node by default, 3-node cluster demonstrated.
  - **Redis** — sessions, cache, rate-limit counters. Nothing else (see ADR 0006/0007
    for the two times Redis was considered for more and rejected).
  - ~~MinIO~~ **SeaweedFS** (see ADR 0015) — S3-compatible object storage: media originals, attachments, raw
    telemetry archive. Swappable for any S3 endpoint by configuration only.

For PostgreSQL HA specifically: **Patroni/Stolon** (more assembly, less
Kubernetes-native) and manual streaming replication (nothing operator-managed to
demonstrate) were rejected in favor of **CloudNativePG**.

## Decision

Five stores, five jobs, node counts as variables — single-node on demo VMs, a cluster
overlay demonstrating the scaled shape.

## Consequences

- Every store must justify its memory on a small VM: heaps and caches are tuned per VM
  class rather than defaulted.
- Revisit when: any single workload's volume dominates — that store scales out first
  (its node-count variable exists for exactly this).
