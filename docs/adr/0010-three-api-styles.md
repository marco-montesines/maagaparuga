# 0010 — Three API styles: REST, gRPC, GraphQL — each where justified

Status: **Accepted**

## Context

The platform's consumers differ: browsers and integrators want plain HTTP/JSON;
high-frequency device telemetry wants compact binary streaming; the dashboard wants
one query across four backends. Using one style for all three means at least two of
them are served badly — but using three styles is only defensible if each is placed
where it genuinely wins.

## Options considered

- **REST everywhere** — simplest; rejected for device ingest (verbose, no streaming)
  and for the dashboard (N round-trips or bespoke aggregation endpoints).
- **gRPC everywhere** — rejected: hostile to browsers and casual integrators.
- **GraphQL everywhere** — rejected: wrong tool for ingest and for simple resource
  CRUD; caching and rate-limiting stories are weaker at the edge.
- **Each style at its strength** ✅.

## Decision

- **REST/JSON** — the default public surface (web, assessment, media) through APISIX.
- **gRPC** — the telemetry service: protobuf contract in `proto/`, client-streaming
  vitals ingest from devices/simulator. APISIX proxies gRPC natively and its
  `grpc-transcode` plugin exposes the *same service* as REST — one implementation, two
  surfaces. OpenFGA permission checks (ADR 0009) are the second production gRPC path.
- **GraphQL** — a single BFF endpoint in the web application (Laravel Lighthouse):
  one dashboard query aggregates the care record (PostgreSQL), the latest vitals window
  (telemetry gRPC), the risk score (assessment), and media search hits (OpenSearch
  hybrid). Aggregation across polyglot services is GraphQL's home turf — it appears
  nowhere else.

## Consequences

- Contracts live in the repo: protobuf for gRPC, the GraphQL schema in the web app;
  CI checks generated-code drift.
- Revisit when: consumer patterns change — e.g. a mobile client might promote GraphQL
  from BFF to primary API.
