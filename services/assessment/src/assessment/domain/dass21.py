"""DASS-21 — Depression Anxiety Stress Scales, 21-item short form.

Standard, published instrument: 21 items across three 7-item subscales, each
item rated 0-3. Because the 21-item form is the short version of the 42-item
DASS, each subscale sum is multiplied by 2 so the severity bands align with the
published DASS-42 norms.

Clean-room implementation of the published scoring — the item text itself is
copyrighted and is NOT stored here; the service scores only the numeric answers
captured in ``questionnaire_responses.answers`` (item id -> value).

Illustrative computation over fictitious data only — not a diagnosis.
"""

from __future__ import annotations

from collections.abc import Mapping

from .models import Dass21Result, Dass21Severity, Dass21Subscale, SubscaleResult

# Item -> subscale assignment (items numbered 1-21, per the published form).
_ITEMS: dict[Dass21Subscale, tuple[int, ...]] = {
    Dass21Subscale.DEPRESSION: (3, 5, 10, 13, 16, 17, 21),
    Dass21Subscale.ANXIETY: (2, 4, 7, 9, 15, 19, 20),
    Dass21Subscale.STRESS: (1, 6, 8, 11, 12, 14, 18),
}

# Severity cut-offs on the (x2) subscale score: (inclusive upper bound, severity),
# checked in order; anything above the last bound is Extremely Severe.
_BANDS: dict[Dass21Subscale, tuple[tuple[int, Dass21Severity], ...]] = {
    Dass21Subscale.DEPRESSION: (
        (9, Dass21Severity.NORMAL),
        (13, Dass21Severity.MILD),
        (20, Dass21Severity.MODERATE),
        (27, Dass21Severity.SEVERE),
    ),
    Dass21Subscale.ANXIETY: (
        (7, Dass21Severity.NORMAL),
        (9, Dass21Severity.MILD),
        (14, Dass21Severity.MODERATE),
        (19, Dass21Severity.SEVERE),
    ),
    Dass21Subscale.STRESS: (
        (14, Dass21Severity.NORMAL),
        (18, Dass21Severity.MILD),
        (25, Dass21Severity.MODERATE),
        (33, Dass21Severity.SEVERE),
    ),
}

_MIN, _MAX = 0, 3


def _severity(subscale: Dass21Subscale, score: int) -> Dass21Severity:
    for upper, severity in _BANDS[subscale]:
        if score <= upper:
            return severity
    return Dass21Severity.EXTREMELY_SEVERE


def _normalise(answers: Mapping[int | str, int]) -> dict[int, int]:
    """Coerce item keys to int and validate the full 1-21 range, each 0-3.
    Raises ValueError rather than scoring a partial/garbage questionnaire."""
    out: dict[int, int] = {}
    for key, value in answers.items():
        try:
            item = int(key)
        except (TypeError, ValueError):
            raise ValueError(f"non-numeric item id: {key!r}") from None
        if not _MIN <= value <= _MAX:
            raise ValueError(f"item {item} value {value} out of range 0-3")
        out[item] = value

    expected = set(range(1, 22))
    missing = sorted(expected - out.keys())
    if missing:
        raise ValueError(f"missing DASS-21 items: {missing}")
    extra = sorted(out.keys() - expected)
    if extra:
        raise ValueError(f"unexpected DASS-21 items: {extra}")
    return out


def _subscale(subscale: Dass21Subscale, answers: dict[int, int]) -> SubscaleResult:
    raw = sum(answers[i] for i in _ITEMS[subscale])
    score = raw * 2
    return SubscaleResult(subscale, raw=raw, score=score, severity=_severity(subscale, score))


def score_dass21(answers: Mapping[int | str, int]) -> Dass21Result:
    """Score a complete set of 21 answers (item id -> 0-3)."""
    a = _normalise(answers)
    return Dass21Result(
        depression=_subscale(Dass21Subscale.DEPRESSION, a),
        anxiety=_subscale(Dass21Subscale.ANXIETY, a),
        stress=_subscale(Dass21Subscale.STRESS, a),
    )
