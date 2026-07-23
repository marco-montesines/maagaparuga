"""DASS-21 scoring — subscale sums, the x2 short-form scaling, published
severity bands, and input validation."""

from __future__ import annotations

import pytest

from assessment.domain.dass21 import score_dass21
from assessment.domain.models import Dass21Severity

DEPRESSION = (3, 5, 10, 13, 16, 17, 21)
ANXIETY = (2, 4, 7, 9, 15, 19, 20)
STRESS = (1, 6, 8, 11, 12, 14, 18)


def answers(default: int = 0, **overrides: int) -> dict[int, int]:
    """21 answers, all ``default`` except the given item overrides."""
    a = {i: default for i in range(1, 22)}
    a.update({int(k): v for k, v in overrides.items()})
    return a


def set_items(items: tuple[int, ...], value: int) -> dict[int, int]:
    return answers(**{str(i): value for i in items})


def test_all_zero_is_normal() -> None:
    result = score_dass21(answers(0))
    for sub in (result.depression, result.anxiety, result.stress):
        assert sub.raw == 0
        assert sub.score == 0
        assert sub.severity is Dass21Severity.NORMAL


def test_all_max_is_extremely_severe() -> None:
    result = score_dass21(answers(3))
    for sub in (result.depression, result.anxiety, result.stress):
        assert sub.raw == 21          # 7 items x 3
        assert sub.score == 42        # x2 short-form scaling
        assert sub.severity is Dass21Severity.EXTREMELY_SEVERE


def test_x2_scaling_only_counts_own_subscale() -> None:
    # Put value 2 on every depression item, zero elsewhere.
    result = score_dass21(set_items(DEPRESSION, 2))
    assert result.depression.raw == 14 and result.depression.score == 28
    assert result.anxiety.score == 0
    assert result.stress.score == 0


@pytest.mark.parametrize(
    # DASS-21 scores are always even (raw x2), so boundary tests use the nearest
    # achievable even score either side of each published cut-off.
    ("score", "severity"),
    [(8, Dass21Severity.NORMAL), (10, Dass21Severity.MILD), (12, Dass21Severity.MILD),
     (14, Dass21Severity.MODERATE), (20, Dass21Severity.MODERATE),
     (22, Dass21Severity.SEVERE), (26, Dass21Severity.SEVERE),
     (28, Dass21Severity.EXTREMELY_SEVERE)],
)
def test_depression_bands(score: int, severity: Dass21Severity) -> None:
    # Build a raw depression sum of score/2 by loading items sequentially.
    raw = score // 2
    a = answers(0)
    for i in DEPRESSION:
        take = min(3, raw)
        a[i] = take
        raw -= take
    assert raw == 0, "test setup: score must be even and <= 42"
    assert score_dass21(a).depression.severity is severity


@pytest.mark.parametrize(
    ("score", "severity"),
    [(6, Dass21Severity.NORMAL), (8, Dass21Severity.MILD),
     (10, Dass21Severity.MODERATE), (14, Dass21Severity.MODERATE),
     (16, Dass21Severity.SEVERE), (18, Dass21Severity.SEVERE),
     (20, Dass21Severity.EXTREMELY_SEVERE)],
)
def test_anxiety_bands(score: int, severity: Dass21Severity) -> None:
    raw = score // 2
    a = answers(0)
    for i in ANXIETY:
        take = min(3, raw)
        a[i] = take
        raw -= take
    assert score_dass21(a).anxiety.severity is severity


@pytest.mark.parametrize(
    ("score", "severity"),
    [(14, Dass21Severity.NORMAL), (16, Dass21Severity.MILD), (18, Dass21Severity.MILD),
     (20, Dass21Severity.MODERATE), (24, Dass21Severity.MODERATE),
     (26, Dass21Severity.SEVERE), (32, Dass21Severity.SEVERE),
     (34, Dass21Severity.EXTREMELY_SEVERE)],
)
def test_stress_bands(score: int, severity: Dass21Severity) -> None:
    raw = score // 2
    a = answers(0)
    for i in STRESS:
        take = min(3, raw)
        a[i] = take
        raw -= take
    assert score_dass21(a).stress.severity is severity


def test_string_keys_accepted() -> None:
    a = {str(i): 0 for i in range(1, 22)}
    assert score_dass21(a).depression.score == 0


def test_missing_item_rejected() -> None:
    a = answers(0)
    del a[7]
    with pytest.raises(ValueError, match="missing DASS-21 items: \\[7\\]"):
        score_dass21(a)


def test_out_of_range_value_rejected() -> None:
    with pytest.raises(ValueError, match="out of range"):
        score_dass21(answers(0, **{"5": 4}))


def test_extra_item_rejected() -> None:
    a = answers(0)
    a[22] = 1
    with pytest.raises(ValueError, match="unexpected DASS-21 items"):
        score_dass21(a)
