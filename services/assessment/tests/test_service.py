"""Service orchestration — scoring runs persist results and raise alerts on
threshold crossings, and surface InsufficientData when inputs are absent."""

from __future__ import annotations

from datetime import datetime

import pytest

from assessment.domain.models import ClinicalRisk, Consciousness, RiskLevel
from assessment.ports import VitalsSampleDTO
from assessment.service import AssessmentService, InsufficientData

from .fakes import FakeStore, FakeVitalsReader, questionnaire

DEPRESSION_ITEMS = (3, 5, 10, 13, 16, 17, 21)


def normal_sample() -> VitalsSampleDTO:
    return VitalsSampleDTO(
        measured_at=datetime(2026, 7, 1, 12, 0),
        respiratory_rate=16, spo2_percent=98, body_temp_c=37.0,
        bp_systolic=120, heart_rate_bpm=70, consciousness=Consciousness.ALERT,
    )


def high_sample() -> VitalsSampleDTO:
    # RR 26 (3) + SpO2 90 (3) + HR 132 (3) = 9 -> NEWS2 high.
    return VitalsSampleDTO(
        measured_at=datetime(2026, 7, 1, 12, 0),
        respiratory_rate=26, spo2_percent=90, body_temp_c=37.0,
        bp_systolic=120, heart_rate_bpm=132, consciousness=Consciousness.ALERT,
    )


def severe_dass() -> dict[int, int]:
    a = {i: 0 for i in range(1, 22)}
    for i in DEPRESSION_ITEMS:
        a[i] = 2  # depression score 28 -> extremely severe
    return a


def test_news2_persists_result_and_alerts_when_high() -> None:
    store = FakeStore()
    svc = AssessmentService(FakeVitalsReader([high_sample()]), store)

    result = svc.assess_news2("cr1")

    assert result.clinical_risk is ClinicalRisk.HIGH
    assert [r["score_type"] for r in store.results] == ["news2"]
    assert store.results[0]["value"] == 9.0
    assert len(store.alerts) == 1
    assert store.alerts[0]["severity"] == "high"


def test_news2_no_alert_when_low() -> None:
    store = FakeStore()
    svc = AssessmentService(FakeVitalsReader([normal_sample()]), store)

    result = svc.assess_news2("cr1")

    assert result.clinical_risk is ClinicalRisk.LOW
    assert len(store.results) == 1
    assert store.alerts == []


def test_news2_insufficient_data_when_window_empty() -> None:
    svc = AssessmentService(FakeVitalsReader([]), FakeStore())
    with pytest.raises(InsufficientData):
        svc.assess_news2("cr1")


def test_dass21_saves_three_results_and_alerts_on_severe() -> None:
    store = FakeStore(questionnaire=questionnaire(severe_dass()))
    svc = AssessmentService(FakeVitalsReader([]), store)

    svc.assess_dass21("cr1")

    types = {r["score_type"] for r in store.results}
    assert types == {"dass21_depression", "dass21_anxiety", "dass21_stress"}
    # Only depression is extremely severe -> exactly one alert.
    assert len(store.alerts) == 1
    assert store.alerts[0]["severity"] == "extremely_severe"


def test_dass21_insufficient_data_when_no_response() -> None:
    svc = AssessmentService(FakeVitalsReader([]), FakeStore())
    with pytest.raises(InsufficientData):
        svc.assess_dass21("cr1")


def test_risk_combines_news2_and_dass21_and_alerts() -> None:
    store = FakeStore(questionnaire=questionnaire(severe_dass()))
    svc = AssessmentService(FakeVitalsReader([high_sample()]), store)

    assessment = svc.assess_risk("cr1")

    assert assessment.level in (RiskLevel.HIGH, RiskLevel.EXTREMELY_HIGH)
    assert assessment.triggers_alert
    assert any(r["score_type"] == "fuzzy_risk" for r in store.results)
    assert len(store.alerts) == 1


def test_risk_insufficient_data_without_questionnaire() -> None:
    svc = AssessmentService(FakeVitalsReader([high_sample()]), FakeStore())
    with pytest.raises(InsufficientData):
        svc.assess_risk("cr1")
