# media — mock imaging/AV pipeline (P4b)

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
  `opensearch_index` (knn + hybrid), `embeddings` (MiniLM). Heavy libraries import
  lazily on first use.
- `worker.py` / `pipeline.py` / `adapters/whisper.py` / `simulator.py` — the
  transcription pipeline (increment 2).

## Roles (one image, `media <cmd>`)

- `media api` — intake + search (the `media` Deployment).
- `media worker` — JetStream consumer (the `media-worker` Deployment; increment 2).
- `media simulate` — seed synthetic mock media (increment 2).

## Develop

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'        # installs the ML stack too (faster-whisper, torch)
pytest -q && ruff check src tests && mypy src
```

The gates need only the light deps; the ML stack is exercised in the worker image.
