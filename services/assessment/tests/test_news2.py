"""NEWS2 scoring — table-driven against the published Royal College of
Physicians chart boundaries, plus aggregate-band and missing-data behaviour."""

from __future__ import annotations

import dataclasses

import pytest

from assessment.domain.models import ClinicalRisk, Consciousness, VitalsSnapshot
from assessment.domain.news2 import score_news2


def normal() -> VitalsSnapshot:
    """A snapshot where every parameter sits in its 0-point band (total 0)."""
    return VitalsSnapshot(
        respiratory_rate=16,
        spo2_percent=98,
        body_temp_c=37.0,
        bp_systolic=120,
        heart_rate_bpm=70,
        consciousness=Consciousness.ALERT,
        on_oxygen=False,
    )


def points_for(param: str, **override: object) -> int:
    result = score_news2(dataclasses.replace(normal(), **override))
    return next(p.points for p in result.parameters if p.name == param)


def test_all_normal_is_zero_low_and_complete() -> None:
    result = score_news2(normal())
    assert result.total == 0
    assert result.clinical_risk is ClinicalRisk.LOW
    assert result.complete
    assert not result.any_parameter_3


@pytest.mark.parametrize(
    ("rr", "pts"),
    [(8, 3), (9, 1), (11, 1), (12, 0), (20, 0), (21, 2), (24, 2), (25, 3)],
)
def test_respiration_bands(rr: int, pts: int) -> None:
    assert points_for("respiration_rate", respiratory_rate=rr) == pts


@pytest.mark.parametrize(
    ("spo2", "pts"),
    [(88, 3), (91, 3), (92, 2), (93, 2), (94, 1), (95, 1), (96, 0), (100, 0)],
)
def test_spo2_scale1_bands(spo2: float, pts: int) -> None:
    assert points_for("spo2", spo2_percent=spo2) == pts


@pytest.mark.parametrize(
    ("temp", "pts"),
    [(34.9, 3), (35.0, 3), (35.1, 1), (36.0, 1), (36.1, 0), (38.0, 0),
     (38.1, 1), (39.0, 1), (39.1, 2), (40.0, 2)],
)
def test_temperature_bands(temp: float, pts: int) -> None:
    assert points_for("temperature", body_temp_c=temp) == pts


@pytest.mark.parametrize(
    ("sbp", "pts"),
    [(90, 3), (91, 2), (100, 2), (101, 1), (110, 1), (111, 0), (219, 0), (220, 3)],
)
def test_systolic_bands(sbp: int, pts: int) -> None:
    assert points_for("systolic_bp", bp_systolic=sbp) == pts


@pytest.mark.parametrize(
    ("hr", "pts"),
    [(40, 3), (41, 1), (50, 1), (51, 0), (90, 0), (91, 1), (110, 1),
     (111, 2), (130, 2), (131, 3)],
)
def test_pulse_bands(hr: int, pts: int) -> None:
    assert points_for("pulse", heart_rate_bpm=hr) == pts


@pytest.mark.parametrize(
    ("level", "pts"),
    [(Consciousness.ALERT, 0), (Consciousness.VOICE, 3),
     (Consciousness.PAIN, 3), (Consciousness.UNRESPONSIVE, 3)],
)
def test_consciousness_bands(level: Consciousness, pts: int) -> None:
    assert points_for("consciousness", consciousness=level) == pts


def test_supplemental_oxygen_adds_two() -> None:
    assert points_for("air_or_oxygen", on_oxygen=False) == 0
    assert points_for("air_or_oxygen", on_oxygen=True) == 2


def test_single_red_flag_is_low_medium_even_when_aggregate_low() -> None:
    # One parameter at 3 (SpO2 91), everything else normal: total 3 but a red flag.
    result = score_news2(dataclasses.replace(normal(), spo2_percent=91))
    assert result.total == 3
    assert result.any_parameter_3
    assert result.clinical_risk is ClinicalRisk.LOW_MEDIUM


def test_aggregate_medium_band() -> None:
    # RR 22 (2) + HR 105 (1) + temp 38.5 (1) + SpO2 92 (2) = 6, no single 3.
    snap = dataclasses.replace(
        normal(), respiratory_rate=22, heart_rate_bpm=105, body_temp_c=38.5, spo2_percent=92
    )
    result = score_news2(snap)
    assert result.total == 6
    assert not result.any_parameter_3
    assert result.clinical_risk is ClinicalRisk.MEDIUM


def test_aggregate_high_band() -> None:
    # RR 26 (3) + SpO2 90 (3) + HR 132 (3) = 9 -> high (emergency response).
    snap = dataclasses.replace(
        normal(), respiratory_rate=26, spo2_percent=90, heart_rate_bpm=132
    )
    result = score_news2(snap)
    assert result.total == 9
    assert result.clinical_risk is ClinicalRisk.HIGH


def test_missing_parameters_named_and_incomplete() -> None:
    # Only two vitals present; the rest are missing.
    result = score_news2(VitalsSnapshot(heart_rate_bpm=70, spo2_percent=98))
    assert not result.complete
    assert set(result.missing) == {
        "respiration_rate", "temperature", "systolic_bp", "consciousness"
    }
    # Present parameters still score; missing ones contribute 0.
    assert result.total == 0


def test_unspecified_consciousness_is_missing() -> None:
    result = score_news2(dataclasses.replace(normal(), consciousness=Consciousness.UNSPECIFIED))
    assert "consciousness" in result.missing
