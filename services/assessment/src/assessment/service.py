"""Assessment orchestration: pull the inputs, run the (pure) scoring, persist the
results, and raise an alert when a score crosses a review threshold.

Alerts route to the web app's alerts inbox for **human review** — this service
never takes an automatic clinical action.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .domain import dass21 as dass21_scoring
from .domain import news2 as news2_scoring
from .domain import risk as risk_scoring
from .domain.models import (
    ClinicalRisk,
    Dass21Result,
    Dass21Severity,
    News2Result,
    RiskAssessment,
)
from .ports import AssessmentStore, VitalsReader
from .snapshot import assemble_snapshot

DASS21_INSTRUMENT = "dass21"
_DASS_ALERT_SEVERITIES = (Dass21Severity.SEVERE, Dass21Severity.EXTREMELY_SEVERE)


class InsufficientData(Exception):
    """The inputs required for a score are not available (no vitals in the
    window, or no questionnaire response)."""


class AssessmentService:
    def __init__(
        self,
        vitals: VitalsReader,
        store: AssessmentStore,
        *,
        window_minutes: int = 60,
        window_limit: int = 500,
        now: type[datetime] | None = None,
    ) -> None:
        self._vitals = vitals
        self._store = store
        self._window = timedelta(minutes=window_minutes)
        self._limit = window_limit
        self._now = now or datetime

    def _utcnow(self) -> datetime:
        return self._now.now(UTC)

    # -- NEWS2 --------------------------------------------------------------

    def assess_news2(self, recipient_id: str) -> News2Result:
        computed_at = self._utcnow()
        samples = self._vitals.window(
            recipient_id, computed_at - self._window, computed_at, self._limit
        )
        snapshot = assemble_snapshot(samples)
        result = news2_scoring.score_news2(snapshot)
        if len(result.missing) == len(result.parameters) - 1:  # only air/oxygen known
            raise InsufficientData("no vitals in the window to score NEWS2")

        result_id = self._store.save_result(
            recipient_id=recipient_id,
            score_type="news2",
            value=float(result.total),
            risk_level=result.clinical_risk.value,
            source="vitals_window",
            computed_at=computed_at,
        )
        # Anything other than routine (LOW) warrants a review.
        if result.clinical_risk is not ClinicalRisk.LOW:
            complete = "" if result.complete else " (partial — some vitals missing)"
            self._store.save_alert(
                recipient_id=recipient_id,
                assessment_result_id=result_id,
                severity=result.clinical_risk.value,
                title=f"NEWS2 {result.clinical_risk.value} (score {result.total})",
                body=f"Early-warning score {result.total} — {result.clinical_risk.value} "
                f"clinical risk{complete}. Illustrative computation, not a diagnosis.",
            )
        return result

    # -- DASS-21 ------------------------------------------------------------

    def assess_dass21(self, recipient_id: str) -> Dass21Result:
        computed_at = self._utcnow()
        response = self._store.latest_questionnaire(recipient_id, DASS21_INSTRUMENT)
        if response is None:
            raise InsufficientData("no DASS-21 questionnaire response on record")

        result = dass21_scoring.score_dass21(response.answers)
        source = f"questionnaire:{response.id}"
        for sub in result.by_subscale().values():
            result_id = self._store.save_result(
                recipient_id=recipient_id,
                score_type=f"dass21_{sub.subscale.value}",
                value=float(sub.score),
                risk_level=sub.severity.value,
                source=source,
                computed_at=computed_at,
            )
            if sub.severity in _DASS_ALERT_SEVERITIES:
                self._store.save_alert(
                    recipient_id=recipient_id,
                    assessment_result_id=result_id,
                    severity=sub.severity.value,
                    title=f"DASS-21 {sub.subscale.value}: {sub.severity.value}",
                    body=f"{sub.subscale.value.title()} score {sub.score} "
                    f"({sub.severity.value}). Illustrative computation, not a diagnosis.",
                )
        return result

    # -- Fuzzy risk (needs both physiological + psychological) --------------

    def assess_risk(self, recipient_id: str) -> RiskAssessment:
        computed_at = self._utcnow()

        samples = self._vitals.window(
            recipient_id, computed_at - self._window, computed_at, self._limit
        )
        news2 = news2_scoring.score_news2(assemble_snapshot(samples))
        if len(news2.missing) == len(news2.parameters) - 1:
            raise InsufficientData("no vitals in the window for the physiological input")

        response = self._store.latest_questionnaire(recipient_id, DASS21_INSTRUMENT)
        if response is None:
            raise InsufficientData("no DASS-21 response for the psychological input")
        dass = dass21_scoring.score_dass21(response.answers)

        assessment = risk_scoring.assess_risk(
            risk_scoring.physiological_index(news2),
            risk_scoring.psychological_index(dass),
        )

        result_id = self._store.save_result(
            recipient_id=recipient_id,
            score_type="fuzzy_risk",
            value=round(assessment.score, 2),
            risk_level=assessment.level.value,
            source=f"vitals_window+questionnaire:{response.id}",
            computed_at=computed_at,
        )
        if assessment.triggers_alert:
            self._store.save_alert(
                recipient_id=recipient_id,
                assessment_result_id=result_id,
                severity=assessment.level.value,
                title=f"Combined risk: {assessment.level.value}",
                body=f"Fuzzy risk index {assessment.score:.0f}/100 "
                f"({assessment.level.value}). Illustrative computation, not a diagnosis.",
            )
        return assessment
