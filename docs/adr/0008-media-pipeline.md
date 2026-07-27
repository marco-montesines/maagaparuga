# 0008 — Media pipeline: faster-whisper speech-to-text, app-side embeddings

Status: **Accepted**

## Context

Mock imaging and audio/video uploads (X-ray, 2D/3D/4D ultrasound, MRI clips,
teleconsultation recordings — all synthetic) must become searchable: transcribed,
chunked, embedded, and indexed with timestamps. The processing runs on CPU-only small
VMs with strict memory budgets.

## Options considered

**Speech-to-text:**

- **Reference openai/whisper** — rejected: several times slower and heavier than the
  CTranslate2 runtime for the same models.
- **Cloud STT APIs (Amazon Transcribe, Azure Speech, …)** — rejected: external data
  flow and per-use cost conflict with a self-contained, no-real-data design.
- **faster-whisper** ✅ — CTranslate2 reimplementation of Whisper; int8 quantization on
  CPU, markedly faster at lower memory; tiny/base models on the demo VMs, larger models
  a documented VM-class upgrade.

**Embedding execution:**

- **Inside OpenSearch (ML Commons local model)** — architecturally elegant (the ingest
  pipeline chunks and embeds; neural queries embed themselves); rejected on a
  single small node: the model shares the OpenSearch process doing search + logs +
  k-NN, is finicky on small heaps, and its memory cannot be capped independently.
  Documented as the alternative for multi-node clusters.
- **App-side sentence-transformers** ✅ — `all-MiniLM-L6-v2` (~90 MB, 384-dim) runs in
  the media worker pod, bounded by Kubernetes limits, sharing the pod with
  faster-whisper (the pipeline is sequential). Query-time embedding uses the same model
  in the media search endpoint.

## Decision

Worker flow: consume job (ADR 0007) → fetch original from the object store → FFmpeg audio
extraction → faster-whisper with segment timestamps → app-side embeddings → OpenSearch
`knn_vector` index (ADR 0006). Intake and worker are separate deployables of one
codebase; uploads ≤ ~50 MB go through the gateway, larger files via object-store presigned
PUT (the threshold is configuration).

## Consequences

- CPU-only, memory-bounded ML that fits the FinOps envelope; model quality scales with
  VM class, not architecture changes.
- The same embedding model must be used at index and query time — pinned deliberately.
- Revisit when: GPU inference or heavier models are justified by real media volume.
