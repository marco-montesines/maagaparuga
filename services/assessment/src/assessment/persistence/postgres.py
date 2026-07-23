"""PostgreSQL implementation of AssessmentStore (psycopg 3).

Reads the latest questionnaire response and writes assessment_results + alerts —
the tables created by the web app's ``create_assessment_tables`` migration.
A short-lived connection per call keeps this simple and correct at this scale;
a pool is the drop-in optimisation if call volume warrants it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..ports import QuestionnaireResponseDTO

_LATEST_QUESTIONNAIRE = """
SELECT id, instrument, answers, submitted_at
FROM questionnaire_responses
WHERE care_recipient_id = %s AND instrument = %s
ORDER BY submitted_at DESC
LIMIT 1
"""

_INSERT_RESULT = """
INSERT INTO assessment_results
    (care_recipient_id, score_type, value, risk_level, source, computed_at,
     created_at, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, now(), now())
RETURNING id
"""

_INSERT_ALERT = """
INSERT INTO alerts
    (care_recipient_id, assessment_result_id, severity, title, body,
     created_at, updated_at)
VALUES (%s, %s, %s, %s, %s, now(), now())
RETURNING id
"""


class PgRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self) -> Any:
        import psycopg

        return psycopg.connect(self._dsn)

    def latest_questionnaire(
        self, recipient_id: str, instrument: str
    ) -> QuestionnaireResponseDTO | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_LATEST_QUESTIONNAIRE, (recipient_id, instrument))
            row = cur.fetchone()
        if row is None:
            return None
        return QuestionnaireResponseDTO(
            id=row[0], instrument=row[1], answers=row[2], submitted_at=row[3]
        )

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
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                _INSERT_RESULT,
                (recipient_id, score_type, value, risk_level, source, computed_at),
            )
            new_id: int = cur.fetchone()[0]
            conn.commit()
        return new_id

    def save_alert(
        self,
        *,
        recipient_id: str,
        assessment_result_id: int,
        severity: str,
        title: str,
        body: str | None,
    ) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                _INSERT_ALERT,
                (recipient_id, assessment_result_id, severity, title, body),
            )
            new_id: int = cur.fetchone()[0]
            conn.commit()
        return new_id
