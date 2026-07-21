# 0011 — Observability: OpenTelemetry → Prometheus / Tempo / OpenSearch → Grafana

Date: 2026-07-20 · Status: **Accepted**

## Context

The platform needs observability with **actionable alerting** — for the infrastructure
and for the system itself (e.g. "vitals ingestion stalled" matters as much as "disk
80% full"). An actionable alert carries current-vs-normal values, the affected
service/endpoint, a dashboard link, and a runbook link.

## Options considered

- **Prometheus + Alertmanager alone** — rejected as the alerting surface: Alertmanager
  routes and groups, but the actionable context (dashboards, unified view across
  metrics/logs/traces, alert history) lives in Grafana unified alerting.
- **The full "LGTM" stack including Loki** — the common default; **Loki rejected**:
  logs already have a home in OpenSearch (ADR 0005/0006), and running a second log
  database on one VM duplicates a store for no capability. Grafana queries OpenSearch
  directly through its data source plugin.
- **Pyroscope (profiling)** — skipped at demonstration scale; documented extension.
- **OpenTelemetry → Prometheus (metrics) + Tempo (traces) + OpenSearch (logs) →
  Grafana unified alerting** ✅.

## Decision

- OpenTelemetry SDKs in all three languages; one request traceable end-to-end:
  APISIX → PHP GraphQL BFF → gRPC telemetry (Go) → assessment (Python).
- Tempo runs single-binary with **the object store (SeaweedFS) as its S3 backend** — no
  new storage system.
- Prometheus scrapes services plus native exporters (node, kube-state, APISIX, NATS,
  PostgreSQL/ClickHouse/OpenSearch/Redis/SeaweedFS); OpenCost feeds cost metrics into the
  same Grafana (FinOps next to latency).
- Dashboards **and alert rules are provisioned as code** in the repository; runbooks
  live in `docs/runbooks/` and alerts link to them.

## Consequences

- One pane (Grafana) for metrics, traces, logs, and cost; alert catalog covers both
  infra (replication lag, disk headroom, gateway 5xx/p95) and system semantics
  (ingest stall, queue backlog, transcription failure rate, failed-login spikes).
- Observability is off by default in the dev overlay, trimmed on ephemeral staging,
  full in production.
- Revisit when: log volume or multi-cluster growth reopens the Loki/OpenSearch
  question on its merits.
