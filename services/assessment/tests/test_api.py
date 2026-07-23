"""API surface — routes return the score, InsufficientData maps to 422, health
is open. Uses the in-memory fakes via dependency override."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from assessment.api import app, get_service
from assessment.ports import VitalsSampleDTO
from assessment.service import AssessmentService

from .fakes import FakeStore, FakeVitalsReader, questionnaire

DEPRESSION_ITEMS = (3, 5, 10, 13, 16, 17, 21)


def client_with(reader: FakeVitalsReader, store: FakeStore) -> TestClient:
    svc = AssessmentService(reader, store)
    app.dependency_overrides[get_service] = lambda: svc
    return TestClient(app)


def high_sample() -> VitalsSampleDTO:
    return VitalsSampleDTO(
        measured_at=datetime(2026, 7, 1, 12, 0),
        respiratory_rate=26, spo2_percent=90, body_temp_c=37.0,
        bp_systolic=120, heart_rate_bpm=132,
    )


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_healthz_open() -> None:
    assert TestClient(app).get("/healthz").json() == {"status": "ok"}


def test_news2_endpoint_returns_score() -> None:
    c = client_with(FakeVitalsReader([high_sample()]), FakeStore())
    resp = c.post("/assess/cr1/news2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 9
    assert body["clinical_risk"] == "high"
    assert body["complete"] in (True, False)


def test_news2_endpoint_422_when_no_vitals() -> None:
    c = client_with(FakeVitalsReader([]), FakeStore())
    resp = c.post("/assess/cr1/news2")
    assert resp.status_code == 422
    assert "vitals" in resp.json()["detail"]


def test_dass21_endpoint_returns_subscales() -> None:
    a = {i: 0 for i in range(1, 22)}
    for i in DEPRESSION_ITEMS:
        a[i] = 2
    c = client_with(FakeVitalsReader([]), FakeStore(questionnaire=questionnaire(a)))
    resp = c.post("/assess/cr1/dass21")
    assert resp.status_code == 200
    body = resp.json()
    assert body["depression"]["severity"] == "extremely_severe"
    assert body["anxiety"]["severity"] == "normal"


def test_risk_endpoint_422_without_questionnaire() -> None:
    c = client_with(FakeVitalsReader([high_sample()]), FakeStore())
    resp = c.post("/assess/cr1/risk")
    assert resp.status_code == 422
