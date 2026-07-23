"""Fuzzy risk inference — corner cases, monotonicity, banding, and the
NEWS2/DASS-21 → input derivation. Exact defuzzified values are not asserted
(they are a property of the membership functions); the behavioural contract is.
"""

from __future__ import annotations

import pytest

from assessment.domain.dass21 import score_dass21
from assessment.domain.models import Consciousness, RiskLevel, VitalsSnapshot
from assessment.domain.news2 import score_news2
from assessment.domain.risk import (
    assess_risk,
    physiological_index,
    psychological_index,
)

DEPRESSION_ITEMS = (3, 5, 10, 13, 16, 17, 21)


def test_both_low_is_very_low_no_alert() -> None:
    r = assess_risk(0, 0)
    assert r.level is RiskLevel.VERY_LOW
    assert not r.triggers_alert


def test_both_high_is_extremely_high_and_alerts() -> None:
    r = assess_risk(20, 10)
    assert r.level is RiskLevel.EXTREMELY_HIGH
    assert r.triggers_alert


@pytest.mark.parametrize(("phys", "psych"), [(12, 0), (0, 10)])
def test_single_high_signal_reaches_high_and_alerts(phys: float, psych: float) -> None:
    # A high NEWS2 alone, or an extremely-severe DASS alone, must cross the
    # referral threshold (early-warning posture).
    r = assess_risk(phys, psych)
    assert r.level in (RiskLevel.HIGH, RiskLevel.EXTREMELY_HIGH)
    assert r.triggers_alert


def test_score_in_range_and_inputs_clamped() -> None:
    r = assess_risk(999, 999)  # far past the universes
    assert 0.0 <= r.score <= 100.0
    assert r.physiological_input == 20  # clamped to _PHYS_MAX
    assert r.psychological_input == 10  # clamped to _PSYCH_MAX
    assert r.level is RiskLevel.EXTREMELY_HIGH


def test_monotonic_in_physiological() -> None:
    scores = [assess_risk(p, 4).score for p in range(0, 21, 2)]
    assert scores == sorted(scores)


def test_monotonic_in_psychological() -> None:
    scores = [assess_risk(8, p).score for p in range(0, 11)]
    assert scores == sorted(scores)


def test_physiological_index_is_news2_total() -> None:
    # RR 26 (3) + SpO2 90 (3) + HR 132 (3) = 9.
    snap = VitalsSnapshot(
        respiratory_rate=26, spo2_percent=90, heart_rate_bpm=132,
        body_temp_c=37.0, bp_systolic=120, consciousness=Consciousness.ALERT,
    )
    news2 = score_news2(snap)
    assert news2.total == 9
    assert physiological_index(news2) == 9


def test_psychological_index_uses_worst_subscale() -> None:
    # All-normal DASS -> 0.
    normal = {i: 0 for i in range(1, 22)}
    assert psychological_index(score_dass21(normal)) == 0

    # Depression items at 2 -> score 28 (extremely severe); others normal.
    worst = {i: 0 for i in range(1, 22)}
    for i in DEPRESSION_ITEMS:
        worst[i] = 2
    dass = score_dass21(worst)
    assert dass.depression.severity.value == "extremely_severe"
    assert psychological_index(dass) == 10.0  # ordinal 4 -> 4 * (10/4)
