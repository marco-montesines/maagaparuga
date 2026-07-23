"""In-memory fakes implementing the ports, for unit-testing the service and API
without ClickHouse, telemetry, or PostgreSQL."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from assessment.ports import QuestionnaireResponseDTO, VitalsSampleDTO


class FakeVitalsReader:
    def __init__(self, samples: Sequence[VitalsSampleDTO]) -> None:
        self._samples = list(samples)

    def window(
        self, recipient_id: str, since: datetime, until: datetime, limit: int
    ) -> Sequence[VitalsSampleDTO]:
        return list(self._samples)


class FakeStore:
    def __init__(self, questionnaire: QuestionnaireResponseDTO | None = None) -> None:
        self.results: list[dict[str, object]] = []
        self.alerts: list[dict[str, object]] = []
        self._questionnaire = questionnaire
        self._next_id = 0

    def latest_questionnaire(
        self, recipient_id: str, instrument: str
    ) -> QuestionnaireResponseDTO | None:
        if self._questionnaire and self._questionnaire.instrument == instrument:
            return self._questionnaire
        return None

    def save_result(
        self,
        *,
        recipient_id: str,
        score_type: str,
        value: float | None,
        risk_level: str | None,
        source: str | None,
        computed_at: datetime,
    ) -> int:
        self._next_id += 1
        self.results.append(
            {"id": self._next_id, "recipient_id": recipient_id, "score_type": score_type,
             "value": value, "risk_level": risk_level, "source": source}
        )
        return self._next_id

    def save_alert(
        self,
        *,
        recipient_id: str,
        assessment_result_id: int,
        severity: str,
        title: str,
        body: str | None,
    ) -> int:
        self.alerts.append(
            {"recipient_id": recipient_id, "assessment_result_id": assessment_result_id,
             "severity": severity, "title": title, "body": body}
        )
        return len(self.alerts)


def questionnaire(answers: Mapping[int | str, int], *, instrument: str = "dass21", rid: int = 1
                  ) -> QuestionnaireResponseDTO:
    return QuestionnaireResponseDTO(
        id=rid, instrument=instrument, answers=answers, submitted_at=datetime(2026, 7, 1)
    )
