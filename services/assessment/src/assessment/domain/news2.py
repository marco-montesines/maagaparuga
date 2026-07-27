"""NEWS2 — the National Early Warning Score 2 (Royal College of Physicians, 2017).

A standard, published early-warning score: each of six physiological parameters
(plus a supplemental-oxygen flag) is banded to 0-3 points; the points sum to an
aggregate that maps to a recommended clinical-response level. This is a
clean-room implementation of the published algorithm — no code or data from any
predecessor system.

Only **SpO2 Scale 1** is implemented (the default for patients without a target
range set for chronic hypercapnic respiratory failure). Scale 2 is a documented
clinical extension, deliberately out of scope here.

Illustrative computation over fictitious data only — not a medical device.
"""

from __future__ import annotations

from .models import (
    ClinicalRisk,
    Consciousness,
    News2Result,
    ParameterScore,
    VitalsSnapshot,
)


def _respiration_points(rr: int) -> int:
    if rr <= 8:
        return 3
    if rr <= 11:
        return 1
    if rr <= 20:
        return 0
    if rr <= 24:
        return 2
    return 3


def _spo2_scale1_points(spo2: float) -> int:
    if spo2 <= 91:
        return 3
    if spo2 <= 93:
        return 2
    if spo2 <= 95:
        return 1
    return 0


def _temperature_points(temp: float) -> int:
    if temp <= 35.0:
        return 3
    if temp <= 36.0:
        return 1
    if temp <= 38.0:
        return 0
    if temp <= 39.0:
        return 1
    return 2


def _systolic_points(sbp: int) -> int:
    if sbp <= 90:
        return 3
    if sbp <= 100:
        return 2
    if sbp <= 110:
        return 1
    if sbp <= 219:
        return 0
    return 3


def _pulse_points(hr: int) -> int:
    if hr <= 40:
        return 3
    if hr <= 50:
        return 1
    if hr <= 90:
        return 0
    if hr <= 110:
        return 1
    if hr <= 130:
        return 2
    return 3


def _consciousness_points(level: Consciousness) -> int:
    # Alert scores 0; any reduced level (V/P/U) or new confusion scores 3.
    return 0 if level is Consciousness.ALERT else 3


def _clinical_risk(total: int, any_parameter_3: bool) -> ClinicalRisk:
    # RCP response banding: a single red (3 in one parameter) warrants urgent
    # review even when the aggregate is otherwise low, so it outranks the 0-4 low
    # band but not the 5-6 / >=7 aggregate bands.
    if total >= 7:
        return ClinicalRisk.HIGH
    if total >= 5:
        return ClinicalRisk.MEDIUM
    if any_parameter_3:
        return ClinicalRisk.LOW_MEDIUM
    return ClinicalRisk.LOW


def score_news2(snapshot: VitalsSnapshot) -> News2Result:
    """Score a vitals snapshot. Missing required parameters are named in the
    result and contribute 0 to the aggregate, so an incomplete score is never
    presented as if it were complete (``result.complete`` is False)."""

    parameters: list[ParameterScore] = []
    missing: list[str] = []

    def add(name: str, value: float | str | None, points: int | None) -> None:
        if points is None:
            missing.append(name)
            parameters.append(ParameterScore(name, value, 0))
        else:
            parameters.append(ParameterScore(name, value, points))

    rr = snapshot.respiratory_rate
    add("respiration_rate", rr, _respiration_points(rr) if rr is not None else None)

    spo2 = snapshot.spo2_percent
    add("spo2", spo2, _spo2_scale1_points(spo2) if spo2 is not None else None)

    # Supplemental oxygen is always known (defaults to air) — never "missing".
    add("air_or_oxygen", "oxygen" if snapshot.on_oxygen else "air", 2 if snapshot.on_oxygen else 0)

    temp = snapshot.body_temp_c
    add("temperature", temp, _temperature_points(temp) if temp is not None else None)

    sbp = snapshot.bp_systolic
    add("systolic_bp", sbp, _systolic_points(sbp) if sbp is not None else None)

    hr = snapshot.heart_rate_bpm
    add("pulse", hr, _pulse_points(hr) if hr is not None else None)

    level = snapshot.consciousness
    known_level = level if level is not None and level is not Consciousness.UNSPECIFIED else None
    add(
        "consciousness",
        known_level.value if known_level else None,
        _consciousness_points(known_level) if known_level else None,
    )

    total = sum(p.points for p in parameters)
    any_parameter_3 = any(p.points == 3 for p in parameters)

    return News2Result(
        total=total,
        parameters=tuple(parameters),
        any_parameter_3=any_parameter_3,
        clinical_risk=_clinical_risk(total, any_parameter_3),
        missing=tuple(missing),
    )
