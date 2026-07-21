# 0004 — Polyglot services: Go, Python, PHP (Laravel + Octane on FrankenPHP)

Date: 2026-07-20 · Status: **Accepted**

## Context

A multi-language platform is only credible if every language is where it is for a
reason — polyglot-for-its-own-sake reads as résumé-driven engineering.

## Options considered

- **Single language for everything** — operationally simplest; rejected: no language is
  best at all three jobs (high-frequency ingest, scientific scoring + media ML, and
  product-surface CRUD), and the platform exists to demonstrate the judgment of
  matching tools to workloads.
- **Per-service assignment by strength** ✅:
  - **Go** — telemetry ingest/read: throughput, concurrency, first-class gRPC.
  - **Python** — assessment (scikit-fuzzy, scoring) and media (FFmpeg tooling,
    faster-whisper, sentence-transformers are Python-first).
  - **PHP** — the product surface, where feature velocity matters most.

For the PHP framework specifically:

- **Symfony** — explicit architecture, strong reputation; rejected: slower to the same
  feature set for this team.
- **Minimal/custom** — rejected: hand-built auth/validation/ORM glue is where security
  mistakes live; wrong trade for a publicly scrutinized repo.
- **Laravel + Octane on FrankenPHP** ✅ — mature batteries (policies, Eloquent,
  seeders, queues); Octane's worker mode on FrankenPHP (a Go application server) keeps
  long-lived workers, and FrankenPHP enables selected PHP functions implemented
  natively in Go.

## Decision

Go telemetry, Python assessment + media, PHP/Laravel web app — each with its own test
and lint lane in CI.

## Consequences

- Three toolchains to maintain; accepted deliberately as part of the demonstration.
- Cross-language concerns (tracing, auth, contracts) must use open standards —
  OpenTelemetry, OIDC/JWT, protobuf (see ADR 0010, 0011).
