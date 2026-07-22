# 0006 — OpenSearch as the vector database

Status: **Accepted**

## Context

The media pipeline produces timestamped transcript segments that must be searchable
both lexically (names, exact phrases) and semantically (differently-worded ideas) —
which requires embeddings and k-NN vector search.

## Options considered

- **Dedicated vector database (Qdrant, Weaviate, …)** — rejected: a sixth stateful
  component on a small VM providing no capability the existing stack lacks.
- **Redis 8 vector search (RedisVL, HNSW)** — capable; rejected to keep Redis at
  exactly one job (sessions/cache) — the one-job-per-store principle (ADR 0005).
- **OpenSearch 3.x in place** ✅ — the current generation provides `knn_vector`
  indexing, ingest pipelines with text chunking and embedding integration, and hybrid
  BM25 + semantic queries with score normalization. Vectors live next to the text they
  index, and next to the metadata filters (speaker, time range, media id) that real
  queries need.

## Decision

OpenSearch 3.x doubles as the vector database. Hybrid search (BM25 + k-NN + filters)
is the query model; every hit deep-links to the source timestamp in the original media.
Speech-to-text always remains external to OpenSearch (ADR 0008).

## Consequences

- Requires staying on the current OpenSearch major (ADR 0013) — older branches lack
  the ingest-time vector features.
- Embedding execution is a separate decision (ADR 0008: app-side).
- Revisit when: vector volume or query latency outgrows what OpenSearch nodes sized
  for search+logs can carry — that is the point to re-price a dedicated vector store.
