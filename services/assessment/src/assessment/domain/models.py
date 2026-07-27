"""Domain types shared by the scoring modules.

Pure data + enums only — no I/O, no framework types — so the scoring logic can
be unit-tested in isolation and reused from the API layer. Every output here is
an illustrative computation over fictitious data (see DISCLAIMER.md); nothing in
this service is a medical device or a substitute for clinical judgement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RiskLevel(StrEnum):
    """Fuzzy risk bands — mirrors ``App\\Enums\\RiskLevel`` in the web app so the
    two sides agree on the stored string values. ``high`` and above raise an
    alert (the SEDS referral threshold)."""

    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREMELY_HIGH = "extremely_high"

    def triggers_alert(self) -> bool:
        return self in (RiskLevel.HIGH, RiskLevel.EXTREMELY_HIGH)


class Consciousness(StrEnum):
    """AVPU level of consciousness — mirrors the telemetry proto ``Consciousness``
    enum. NEWS2 scores any state other than ``alert`` (new-onset confusion or a
    reduced level) at 3 points."""

    UNSPECIFIED = "unspecified"
    ALERT = "alert"
    VOICE = "voice"
    PAIN = "pain"
    UNRESPONSIVE = "unresponsive"


@dataclass(frozen=True, slots=True)
class VitalsSnapshot:
    """One consolidated set of vital signs for a care recipient at a point in
    time — the input to NEWS2. Assembled by the caller from a telemetry window
    (single-purpose devices each report a subset, so the latest non-null value of
    each parameter across the window is taken). Every field is optional because a
    reading may simply not have been taken; NEWS2 reports which required
    parameters are missing rather than guessing.

    ``on_oxygen`` is not part of the device vitals contract (devices report raw
    measurements, not the care context), so it defaults to breathing air; a
    caller that knows supplemental oxygen is in use passes ``True``.
    """

    respiratory_rate: int | None = None      # breaths per minute
    spo2_percent: float | None = None        # oxygen saturation %
    body_temp_c: float | None = None         # degrees Celsius
    bp_systolic: int | None = None           # mmHg
    heart_rate_bpm: int | None = None        # beats per minute
    consciousness: Consciousness | None = None
    on_oxygen: bool = False


class ClinicalRisk(StrEnum):
    """NEWS2 aggregate clinical-risk banding (Royal College of Physicians): the
    recommended monitoring/response level for a total score."""

    LOW = "low"
    LOW_MEDIUM = "low_medium"   # a single parameter scoring 3 — a localised red flag
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class ParameterScore:
    """The NEWS2 sub-score for one parameter (0-3), with the measured value for
    traceability."""

    name: str
    value: float | str | None
    points: int


@dataclass(frozen=True, slots=True)
class News2Result:
    """A complete NEWS2 assessment: the aggregate total, the per-parameter
    breakdown, whether any single parameter hit the red-flag 3, the clinical-risk
    band, and any required parameters that were missing (so a partial score is
    never silently presented as complete)."""

    total: int
    parameters: tuple[ParameterScore, ...]
    any_parameter_3: bool
    clinical_risk: ClinicalRisk
    missing: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.missing


class Dass21Subscale(StrEnum):
    DEPRESSION = "depression"
    ANXIETY = "anxiety"
    STRESS = "stress"


class Dass21Severity(StrEnum):
    NORMAL = "normal"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREMELY_SEVERE = "extremely_severe"


@dataclass(frozen=True, slots=True)
class SubscaleResult:
    subscale: Dass21Subscale
    raw: int        # sum of the 7 items (each 0-3)
    score: int      # raw * 2 (DASS21 is the short form; x2 aligns with DASS42 bands)
    severity: Dass21Severity


@dataclass(frozen=True, slots=True)
class Dass21Result:
    depression: SubscaleResult
    anxiety: SubscaleResult
    stress: SubscaleResult

    def by_subscale(self) -> dict[Dass21Subscale, SubscaleResult]:
        return {r.subscale: r for r in (self.depression, self.anxiety, self.stress)}


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Output of the fuzzy-risk inference: a crisp risk index (0-100,
    defuzzified) and the ``RiskLevel`` band it falls in. ``high`` and above set
    the referral flag (routes to the alerts inbox for human review — never an
    automatic action)."""

    level: RiskLevel
    score: float                 # defuzzified crisp risk, 0-100
    physiological_input: float   # the physiological signal fed in (NEWS2-derived)
    psychological_input: float   # the psychological signal fed in (DASS-21-derived)

    @property
    def triggers_alert(self) -> bool:
        return self.level.triggers_alert()
