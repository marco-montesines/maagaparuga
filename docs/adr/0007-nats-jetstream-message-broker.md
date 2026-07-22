# 0007 — NATS JetStream as the message broker

Status: **Accepted**

## Context

Device-facing ingest (vitals events, media uploads) must be decoupled from processing
so that bursts from a large device fleet buffer in a queue instead of overwhelming
services. The broker carries **references, never binaries** (claim-check: originals go
to the object store, messages carry object keys), and ClickHouse is written only by a batching
consumer. The workload has two shapes: an event stream (vitals) and a **work queue**
(media processing jobs needing per-message ack, redelivery caps, poison-job handling).

## Options considered

- **Kafka** — the canonical fleet-scale streaming platform; rejected *here* because its
  distinguishing benefits are multi-node properties (partition parallelism across
  brokers, replication, the Connect/Streams ecosystem) that do not materialize on a
  single-node deployment — while its costs (JVM broker, 1–2 GB+ heap, KRaft controller,
  large tuning surface) are immediate. A single-broker Kafka is Kafka's cost without
  Kafka's benefit.
- **Redpanda** — Kafka API without the JVM; still rejected *now*: (1) ~1–2 GB
  thread-per-core C++ engine vs tens of MB for NATS — an order of magnitude, not a
  rounding error; (2) its differentiator is the Kafka API/ecosystem, worth nothing on
  one node with no consumer ecosystem attached; (3) Kafka-model logs track offsets, not
  per-message acks — work-queue semantics (media jobs) must be built on top, where
  JetStream has them natively; (4) no native MQTT; (5) Community Edition is BSL 1.1 —
  source-available, not OSI open source today, which weakens the fully-open-source
  story.
- **RabbitMQ** — solid work-queue semantics; rejected: heavier footprint and no
  equivalent combined streaming + MQTT story.
- **Redis Streams** — zero new components; rejected to keep Redis single-purpose
  (ADR 0005).
- **NATS JetStream** ✅ — single lightweight Go binary (Apache-2.0, CNCF), at-least-once
  delivery with durable consumers, native work-queue semantics (per-message ack,
  max-deliveries), horizontal consumer scaling, and a **native MQTT listener** — the
  protocol real IoT fleets speak — with no extra component.

## Decision

NATS JetStream carries the vitals event stream and the media job queue. Publishers and
consumers sit behind a thin messaging layer with protobuf payloads, so the broker is a
bounded swap.

## Consequences

- Fits the demonstration footprint (a lightweight Go binary per node vs a JVM broker); MQTT device ingest is available without new
  infrastructure.
- **Revisit when** the platform needs multi-node streaming as a baseline: sustained
  high-throughput partitioned streams, long replayable retention for multiple
  independent consumer groups, or stream-processing/Connect ecosystems. At that point
  choose **Kafka** (pure Apache-2.0, the ecosystem standard) or **Redpanda** (Kafka API
  without a JVM fleet, if its licensing is acceptable) — the seam is designed for that
  swap.
