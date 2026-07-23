"""Fuzzy risk inference — a SEDS-inspired, clean-room Mamdani system.

The predecessor concept (SEDS, published method) fed many physiological and
emotional/behavioural signals into a MATLAB Mamdani inference to produce a single
mental-health-risk level. This is an **independent reimplementation of the
concept** (never the paper's code, tables, or figures) using scikit-fuzzy, and
deliberately reduced to two well-founded inputs that the platform actually has:

  * a **physiological** signal — the NEWS2 aggregate (0-20), which already uses
    the validated Royal College of Physicians bands; and
  * a **psychological** signal — a 0-10 index derived from the worst DASS-21
    subscale severity.

Two antecedents → one risk consequent, banded to the five ``RiskLevel`` values.
`high` and above set the referral flag, which routes to the alerts inbox for
**human review** — never an automatic action (a deliberate departure from the
SEDS auto-SMS referral; MDR caution). Extensible: more antecedents (GSR, skin
pH, activity) slot in as the mock device surface grows.

Illustrative computation over fictitious data only — not a diagnosis.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

from .models import Dass21Result, Dass21Severity, News2Result, RiskAssessment, RiskLevel

# Physiological universe = NEWS2 aggregate range; psychological = 0-10 index;
# risk output = 0-100. Bands on the crisp defuzzified risk -> RiskLevel.
_PHYS_MAX = 20
_PSYCH_MAX = 10
_RISK_MAX = 100

_SEVERITY_ORDINAL: dict[Dass21Severity, int] = {
    Dass21Severity.NORMAL: 0,
    Dass21Severity.MILD: 1,
    Dass21Severity.MODERATE: 2,
    Dass21Severity.SEVERE: 3,
    Dass21Severity.EXTREMELY_SEVERE: 4,
}

# Crisp-risk -> RiskLevel bands (upper bound inclusive; last is open-ended).
_RISK_BANDS: tuple[tuple[float, RiskLevel], ...] = (
    (20, RiskLevel.VERY_LOW),
    (40, RiskLevel.LOW),
    (60, RiskLevel.MODERATE),
    (80, RiskLevel.HIGH),
)


@lru_cache(maxsize=1)
def _control_system() -> ctrl.ControlSystem:
    """Build the fuzzy control system once (membership functions + rule base).
    Cached because assembly is relatively expensive; each evaluation gets its own
    lightweight simulation."""
    phys = ctrl.Antecedent(np.arange(0, _PHYS_MAX + 1, 1), "physiological")
    psych = ctrl.Antecedent(np.arange(0, _PSYCH_MAX + 1, 1), "psychological")
    risk = ctrl.Consequent(np.arange(0, _RISK_MAX + 1, 1), "risk")

    # Physiological bands roughly track the NEWS2 clinical bands (0-4 low,
    # 5-6 medium, 7+ high).
    phys["low"] = fuzz.trapmf(phys.universe, [0, 0, 3, 5])
    phys["medium"] = fuzz.trimf(phys.universe, [4, 6, 8])
    phys["high"] = fuzz.trapmf(phys.universe, [7, 10, _PHYS_MAX, _PHYS_MAX])

    psych["low"] = fuzz.trapmf(psych.universe, [0, 0, 2.5, 4])
    psych["medium"] = fuzz.trimf(psych.universe, [3.5, 5, 6.5])
    psych["high"] = fuzz.trapmf(psych.universe, [6, 7.5, _PSYCH_MAX, _PSYCH_MAX])

    risk["very_low"] = fuzz.trimf(risk.universe, [0, 0, 25])
    risk["low"] = fuzz.trimf(risk.universe, [0, 25, 50])
    risk["moderate"] = fuzz.trimf(risk.universe, [25, 50, 75])
    risk["high"] = fuzz.trimf(risk.universe, [50, 75, 100])
    risk["extremely_high"] = fuzz.trimf(risk.universe, [75, 100, 100])

    # Rule matrix (physiological x psychological -> risk). Monotonic (raising
    # either input never lowers the risk) and deliberately conservative for an
    # early-warning tool: a SINGLE high signal — a high NEWS2 *or* an
    # extremely-severe DASS subscale — reaches `high` and thus the referral
    # threshold, without waiting for both to be elevated. Both high -> extreme.
    rules = [
        ctrl.Rule(phys["low"] & psych["low"], risk["very_low"]),
        ctrl.Rule(phys["low"] & psych["medium"], risk["low"]),
        ctrl.Rule(phys["low"] & psych["high"], risk["high"]),
        ctrl.Rule(phys["medium"] & psych["low"], risk["low"]),
        ctrl.Rule(phys["medium"] & psych["medium"], risk["moderate"]),
        ctrl.Rule(phys["medium"] & psych["high"], risk["high"]),
        ctrl.Rule(phys["high"] & psych["low"], risk["high"]),
        ctrl.Rule(phys["high"] & psych["medium"], risk["high"]),
        ctrl.Rule(phys["high"] & psych["high"], risk["extremely_high"]),
    ]
    return ctrl.ControlSystem(rules)


def _band(score: float) -> RiskLevel:
    for upper, level in _RISK_BANDS:
        if score <= upper:
            return level
    return RiskLevel.EXTREMELY_HIGH


def _clamp(value: float, hi: float) -> float:
    return max(0.0, min(float(value), hi))


def physiological_index(news2: News2Result) -> float:
    """The physiological signal for the fuzzy system: the NEWS2 aggregate.
    (Only meaningful when the NEWS2 score is complete; the caller decides.)"""
    return _clamp(news2.total, _PHYS_MAX)


def psychological_index(dass: Dass21Result) -> float:
    """The psychological signal: the worst of the three DASS-21 subscale
    severities, mapped from its 0-4 ordinal onto the 0-10 input scale (the worst
    subscale drives distress)."""
    worst = max(_SEVERITY_ORDINAL[s.severity] for s in dass.by_subscale().values())
    return worst * (_PSYCH_MAX / 4)


def assess_risk(physiological: float, psychological: float) -> RiskAssessment:
    """Run the Mamdani inference for the two crisp inputs and band the result."""
    phys = _clamp(physiological, _PHYS_MAX)
    psych = _clamp(psychological, _PSYCH_MAX)

    sim = ctrl.ControlSystemSimulation(_control_system())
    sim.input["physiological"] = phys
    sim.input["psychological"] = psych
    sim.compute()
    score = float(sim.output["risk"])

    return RiskAssessment(
        level=_band(score),
        score=score,
        physiological_input=phys,
        psychological_input=psych,
    )
