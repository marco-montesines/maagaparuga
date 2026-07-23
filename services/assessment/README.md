# services/assessment — Scoring service (Python)

Early-warning score computation, questionnaire scoring, and fuzzy-logic risk
levels over telemetry windows and questionnaire responses; scores and referral
flags are written to PostgreSQL for the web application's alerts inbox.

All outputs are illustrative computations over fictitious data — not a medical
device, not a diagnosis. See [DISCLAIMER.md](../../DISCLAIMER.md).

## Scoring (`src/assessment/domain/` — pure, no I/O)

Clean-room implementations of published algorithms; no code/data from any
predecessor system, and copyrighted questionnaire item text is never stored
(only numeric answers are scored).

- **NEWS2** (`news2.py`) — National Early Warning Score 2 (Royal College of
  Physicians). Six vitals + supplemental-oxygen flag → 0-3 points each →
  aggregate → clinical-risk band (low / low-medium / medium / high). SpO2
  Scale 1; Scale 2 (chronic hypercapnic respiratory failure) is out of scope.
  Missing parameters are named, so a partial score is never presented as
  complete. **Done, table-driven tests against the published chart.**
- **DASS-21** (`dass21.py`) — 3 subscales × 7 items, ×2 short-form scaling,
  standard severity bands. Validates the full 1-21 range. **Done, tested.**
- **Fuzzy risk** (`risk.py`) — scikit-fuzzy Mamdani, SEDS-inspired clean-room:
  two antecedents — **physiological** (NEWS2 aggregate) × **psychological**
  (worst DASS-21 subscale severity) → risk consequent, defuzzified and banded to
  the five `RiskLevel` values. Conservative for early warning: a single high
  signal reaches `high` and the referral threshold; `high`+ routes to the alerts
  inbox for **human review** (never an automatic action — MDR caution).
  **Done, tested (corners, monotonicity, banding, input derivation).**

## Reading vitals — two selectable adapters (`VITALS_READER`)

The service reads a vitals window behind a `VitalsReader` interface; both
adapters ship, chosen by config:

- **`clickhouse`** (default) — a direct **read-only** query. Telemetry still owns
  the write path; ClickHouse is built for many read-only analytical consumers.
  Couples to the vitals table's columns.
- **`grpc`** — telemetry's `VitalsService/GetWindow`. Depends only on the proto
  contract (stubs under `src/assessment/gen/`, regenerate with
  `python -m grpc_tools.protoc`); presents the assessment service's bearer token.

## Status

**In progress (P4).** Built: the full scoring core (NEWS2 + DASS-21 + fuzzy risk),
the FastAPI surface, the orchestration + persistence (`assessment_results` +
`alerts`), and **both** vitals readers — `pytest` (109 tests) + `ruff` +
`mypy --strict` green. Next: a Dockerfile, the deployment wiring (image + probes
+ env + the assessment service identity for the gRPC reader), and an end-to-end
`make` demo.

## Development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'      # or: pip install pytest ruff mypy  (core is stdlib-only)
pytest -q
ruff check src tests
mypy src
```
