# REST APIs — media & assessment

Two services expose plain HTTP/JSON (FastAPI) surfaces through the gateway: the
**media** pipeline (upload intake + hybrid search) and the **assessment**
scoring service. Sources: `services/media/src/media/api.py`,
`services/assessment/src/assessment/api.py`.

> **Research/educational framework — not a medical device.** All media is
> synthetic mock media; all scores are **illustrative**, computed from mock
> data. Never upload real personal or health data. See
> [`DISCLAIMER.md`](https://github.com/marco-montesines/maagaparuga/blob/master/DISCLAIMER.md).

---

## Media service

Accepts (mock) imaging and audio/video uploads, catalogues them, and — for
recorded consultations — transcribes and indexes them for hybrid search. Reached
through the gateway, which rewrites `/v1/media*` to the service's own paths.

| Gateway path | Method | Service path | Purpose |
|---|---|---|---|
| `/v1/media` | `POST` | `/media` | upload a mock media asset |
| `/v1/media/{asset_id}` | `GET` | `/media/{asset_id}` | fetch an asset's catalog entry |
| `/v1/media/search` | `GET` | `/search` | hybrid search over transcripts |
| — | `GET` | `/healthz` | liveness (`{"status": "ok"}`) |

### Authentication & authorization

Controlled by the media service's `AUTH_MODE`:

- **`AUTH_MODE=jwt`** — the caller's ZITADEL bearer is verified against the JWKS,
  then **OpenFGA** gates the care recipient: reads need **`viewer`**, writes need
  **`editor`** (mirrors the telemetry model). A missing/invalid bearer → `401`;
  a valid caller without the relationship → `403` on writes and search, and
  `404` on a single-asset `GET` (so the response does not reveal that an asset
  exists to a caller with no relationship to its care recipient). Cloud
  deployments run this mode.
- **`AUTH_MODE=disabled`** *(dev default)* — skips JWT + OpenFGA, warns loudly at
  startup, allows every request. For local demos only.

At the gateway, the `/v1/media*` routes are additionally edge-authenticated
(valid bearer required), so the edge proves the caller holds a valid token and
the service proves they may act on that care recipient.

### `POST /v1/media` — upload

`multipart/form-data`:

| Field | Type | Notes |
|---|---|---|
| `care_recipient_id` | integer ≥ 1 | form field |
| `kind` | enum | one of `xray`, `ultrasound_2d`, `ultrasound_3d`, `ultrasound_4d`, `mri`, `teleconsult` |
| `file` | file | the mock media binary |

Behaviour: the body is streamed with a running size cap
(`MAX_UPLOAD_BYTES`, default 50 MiB) — exceeding it → `413`; an empty upload →
`400`. Only `teleconsult` assets carry an audio track and get transcribed;
imaging kinds are catalogued but skipped for transcription.

Response `201`:

```json
{
  "id": "6f1c...uuid",
  "care_recipient_id": 1,
  "kind": "teleconsult",
  "filename": "mock-consult.wav",
  "content_type": "audio/wav",
  "size_bytes": 20480,
  "status": "uploaded"
}
```

`status` is one of `uploaded`, `processing`, `indexed`, `skipped`, `failed`.

```bash
curl -X POST https://<gateway-host>/v1/media \
  -H "Authorization: Bearer $TOKEN" \
  -F "care_recipient_id=1" \
  -F "kind=teleconsult" \
  -F "file=@mock-consult.wav"
```

### `GET /v1/media/{asset_id}` — fetch catalog entry

`asset_id` is a UUID; a non-UUID or unknown/unauthorized asset → `404`. Response
is the same shape as the upload response.

```bash
curl https://<gateway-host>/v1/media/6f1c...uuid \
  -H "Authorization: Bearer $TOKEN"
```

### `GET /v1/media/search` — hybrid search

Query parameters:

| Param | Type | Notes |
|---|---|---|
| `q` | string (min length 1) | the search query |
| `care_recipient_id` | integer ≥ 1 | **required** — you can only search a recipient you may view |
| `limit` | integer 1–50 | default `10` |

`care_recipient_id` is required and authorized: a caller can only search
transcripts for a recipient they may view, never "everyone's".

Response:

```json
{
  "query": "shortness of breath",
  "hits": [
    {
      "asset_id": "6f1c...uuid",
      "care_recipient_id": 1,
      "index": 3,
      "start_ms": 12000,
      "end_ms": 15000,
      "text": "reports shortness of breath after walking",
      "score": 0.82
    }
  ]
}
```

```bash
curl "https://<gateway-host>/v1/media/search?care_recipient_id=1&q=shortness+of+breath&limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Assessment service

Computes scores for a care recipient from vitals (read via ClickHouse or the
telemetry gRPC API) and questionnaire inputs, persists the result, and raises a
human-review alert when a threshold is crossed. **Scores are illustrative, not
diagnostic.**

| Path | Method | Purpose |
|---|---|---|
| `/assess/{recipient_id}/news2` | `POST` | NEWS2 early-warning score |
| `/assess/{recipient_id}/dass21` | `POST` | DASS-21 questionnaire subscales |
| `/assess/{recipient_id}/risk` | `POST` | fuzzy-logic composite risk level |
| `/healthz` | `GET` | liveness (`{"status": "ok"}`) |

`recipient_id` is a path parameter (string). A scoring run whose inputs are not
yet available returns **`422`** with a `{"detail": "..."}` body.

> **Auth note:** the assessment routes carry **no caller authentication or
> per-recipient authorization in the service code itself** — unlike telemetry
> and media, this service has no `AUTH_MODE` and performs no JWT/OpenFGA check on
> these endpoints. Treat it as a platform-internal service and place any edge
> protection at the gateway.

### `POST /assess/{recipient_id}/news2`

```bash
curl -X POST https://<gateway-host>/assess/1/news2
```

Response:

```json
{
  "total": 4,
  "clinical_risk": "medium",
  "any_parameter_3": false,
  "complete": true,
  "missing": [],
  "parameters": [
    {"name": "heart_rate", "value": 72, "points": 0},
    {"name": "spo2", "value": 94, "points": 2}
  ]
}
```

- `total` — summed NEWS2 points.
- `clinical_risk` — banding label.
- `any_parameter_3` — whether any single parameter scored 3.
- `complete` / `missing` — whether every input was available, and which were not.
- `parameters` — per-parameter `{name, value, points}` (`value` may be a number,
  a string, or null).

### `POST /assess/{recipient_id}/dass21`

```json
{
  "depression": {"raw": 6, "score": 12, "severity": "mild"},
  "anxiety":    {"raw": 4, "score": 8,  "severity": "normal"},
  "stress":     {"raw": 8, "score": 16, "severity": "moderate"}
}
```

Each subscale carries the `raw` sum, the DASS-21 `score` (raw doubled), and a
`severity` band.

### `POST /assess/{recipient_id}/risk`

```json
{
  "level": "elevated",
  "score": 0.63,
  "triggers_alert": true,
  "physiological_input": 0.7,
  "psychological_input": 0.5
}
```

- `level` — the fuzzy-logic risk band.
- `score` — composite risk (rounded to 2 decimals).
- `triggers_alert` — whether this run raised a human-review alert.
- `physiological_input` / `psychological_input` — the two normalized inputs the
  fuzzy system combined.

```bash
curl -X POST https://<gateway-host>/assess/1/risk
```
