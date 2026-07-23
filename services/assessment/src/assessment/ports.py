"""Ports — the interfaces the service depends on, and the DTOs that cross them.

The service logic is written against these ``Protocol``s, so the vitals source
(direct ClickHouse read vs. telemetry gRPC) and the database are swappable
adapters, and the logic is unit-tested with in-memory fakes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .domain.models import Consciousness


@dataclass(frozen=True, slots=True)
class VitalsSampleDTO:
    """One vitals sample as returned by a VitalsReader — a subset of the
    telemetry contract, provider-agnostic (the ClickHouse and gRPC adapters both
    map onto this)."""

    measured_at: datetime
    device_id: str | None = None
    respiratory_rate: int | None = None
    spo2_percent: float | None = None
    body_temp_c: float | None = None
    bp_systolic: int | None = None
    bp_diastolic: int | None = None
    heart_rate_bpm: int | None = None
    consciousness: Consciousness | None = None


@dataclass(frozen=True, slots=True)
class QuestionnaireResponseDTO:
    id: int
    instrument: str
    answers: Mapping[int | str, int]
    submitted_at: datetime


class VitalsReader(Protocol):
    """Reads a time window of vitals for a care recipient, newest first."""

    def window(
        self, recipient_id: str, since: datetime, until: datetime, limit: int
    ) -> Sequence[VitalsSampleDTO]: ...


class AssessmentStore(Protocol):
    """Reads questionnaire responses and writes assessment results + alerts
    (the tables in ``create_assessment_tables``)."""

    def latest_questionnaire(
        self, recipient_id: str, instrument: str
    ) -> QuestionnaireResponseDTO | None: ...

    def save_result(
        self,
        *,
        recipient_id: str,
        score_type: str,
        value: float | None,
        risk_level: str | None,
        source: str | None,
        computed_at: datetime,
    ) -> int: ...

    def save_alert(
        self,
        *,
        recipient_id: str,
        assessment_result_id: int,
        severity: str,
        title: str,
        body: str | None,
    ) -> int: ...
