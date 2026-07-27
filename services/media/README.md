# media — mock imaging/AV pipeline

Python/FastAPI service that ingests **synthetic** imaging and audio/video media,
transcribes recorded consultations, and makes them searchable. No real clinical
media, ever — `data/mock` only.

## Flow

```
upload ─▶ [API]  store binary (SeaweedFS, claim-check) ─▶ catalog row (PostgreSQL)
                 └─ recorded consult? publish job to NATS JetStream ─┐
                                                                     ▼
                 [worker]  fetch binary ─▶ FFmpeg audio ─▶ faster-whisper segments
                           └─▶ MiniLM embeddings ─▶ OpenSearch knn_vector index
search ◀─ [API]  embed query ─▶ hybrid (BM25 + k-NN) over OpenSearch ◀────────────┘
```

Imaging kinds (X-ray, 2D/3D/4D ultrasound, MRI) have no audio track: they are
catalogued as `skipped` and never queued. Only `teleconsult` recordings are
transcribed.

## Layout (ports + adapters, same lane as `services/assessment`)

- `domain/models.py` — `MediaKind`, `MediaAsset`, `ProcessingJob` (claim-check),
  `TranscriptSegment`.
- `ports.py` — `ObjectStore`, `Catalog`, `JobQueue`, `TranscriptIndex`,
  `Transcriber`, `Embedder` Protocols. Tests use fakes, so the fast suite never
  imports boto3/torch/etc.
- `api.py` — `POST /media` (upload), `GET /media/{id}`, `GET /search`, `/healthz`.
- `service.py` — intake + search orchestration (blocking adapters run in a thread).
- `adapters/` — `s3` (SeaweedFS), `catalog_postgres`, `queue_nats` (JetStream),
  `opensearch_index` (knn + hybrid), `embeddings` (MiniLM), `whisper`
  (faster-whisper). Heavy libraries import lazily on first use.
- `worker.py` / `pipeline.py` — the JetStream consumer + transcription pipeline
  (fetch → FFmpeg normalize → faster-whisper → MiniLM → OpenSearch). The FFmpeg
  step is an injected seam, so the pipeline is unit-tested with fakes.
- `simulator.py` — synthesizes fictitious consultation speech (espeak-ng) +
  imaging placeholders and uploads them to the intake API.

## Roles (one image, `media <cmd>`)

- `media api` — intake + search (the `media` Deployment, port 8000).
- `media worker` — JetStream consumer (the `media-worker` Deployment; liveness on
  `:9091`, model cache on a PVC at `/models`).
- `media simulate` — seed synthetic mock media (`make dev-media`).

## Develop

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'        # installs the ML stack too (faster-whisper, torch)
pytest -q && ruff check src tests && mypy src
```

The gates need only the light deps; the ML stack is exercised in the worker image.
