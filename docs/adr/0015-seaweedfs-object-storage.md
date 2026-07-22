# 0015 — SeaweedFS replaces MinIO (upstream discontinued)

Status: **Accepted** · Supersedes the object-store choice in
[ADR 0005](0005-right-store-per-workload.md)

## Context

One day after ADR 0005 selected MinIO as the S3-compatible object store, a
maintenance check surfaced that the **MinIO community edition is discontinued**:
the `minio/minio` GitHub repository is archived and its README states
"THIS REPOSITORY IS NO LONGER MAINTAINED", with distribution now source-only
(container images stopped mid-2025) and users directed to the
commercial AIStor products. Pinning a latest-stable that can never move again
violates ADR 0013, and an unmaintained storage engine is not a defensible
foundation.

This is exactly the scenario ADRs exist for: a decision reopened by upstream
reality, re-evaluated on its merits, and superseded in the open.

## Options considered

| Option | Assessment |
|---|---|
| Stay on frozen MinIO ❌ | No maintenance, no CVE response, images already stale — indefensible for a public platform |
| AIStor (commercial MinIO successor) ❌ | Vendor-supported but conflicts with the fully-open-source goal |
| **Garage** (AGPL-3.0, Rust) | Excellent lightweight fit for single-node self-hosting — the "right-sized" pick by this repo's usual reasoning. Passed over here for SeaweedFS's longer production track record and Apache-2.0 license; remains the documented alternative for minimal deployments |
| RustFS ❌ | MinIO-like ergonomics but a young project — replacing a discontinued store with an unproven one repeats the risk |
| Ceph RGW ❌ | The enterprise standard, but operationally heavy — plainly overkill for this footprint |
| **SeaweedFS** ✅ (Apache-2.0, Go) | Production-proven at scale over many years, very active development, S3 API (works with Laravel `Storage`, presigned uploads, Tempo). Single-binary all-in-one mode (`weed server -s3`) fits one small VM; scales out by splitting master/volume/filer roles with replication and erasure coding |

Two SeaweedFS capabilities also weighed in (as documented growth paths, not
demo-scale claims):

- **Transparent cloud tiering** — hot data local, warm data on any cloud object
  storage with O(1) access; pairs naturally with Hetzner Object Storage and the
  FinOps posture (cheap elastic capacity without changing the app-facing S3 seam).
- **Built-in Iceberg REST Catalog** — the same cluster can serve Iceberg tables
  to Spark/Trino/DuckDB etc. without a Hive Metastore or Glue; a self-contained
  lakehouse path if the analytics story ever grows beyond ClickHouse.

## Decision

SeaweedFS in single-binary mode (`weed server -s3`) is the platform's object
store: media originals, attachments, raw telemetry archive, Tempo traces.
S3 credentials via `-s3.config`; buckets bootstrapped by a one-shot `weed shell`
job. The cluster overlay splits roles and adds replication.

The swap itself validated ADR 0005's claim that the object store is replaceable
by configuration: **no service code changed** — only the endpoint, credentials,
and deployment manifests.

## Consequences

- License improves for the fully-open-source story (Apache-2.0 vs MinIO's AGPL).
- Operational surface is somewhat larger than MinIO's was (master/volume/filer
  concepts exist even in all-in-one mode) — accepted for the maturity gained.
- A standing lesson for ADR 0013's version policy: "latest stable, pinned" must
  include *is upstream alive* as part of the dependency-update review.
- Revisit when: scale demands split roles/erasure coding (built-in), cloud
  tiering becomes cost-effective (built-in), or the lakehouse path is wanted
  (built-in Iceberg catalog).
