"""gRPC reader — the VitalsSample -> DTO mapping (optional-field presence and
the consciousness enum). No live server; the proto message is built directly."""

from __future__ import annotations

from datetime import UTC, datetime

from assessment.domain.models import Consciousness
from assessment.gen.maagaparuga.telemetry.v1 import vitals_pb2
from assessment.readers.grpc import sample_to_dto


def test_maps_present_fields() -> None:
    s = vitals_pb2.VitalsSample(
        device_id="d1", care_recipient_id="1",
        heart_rate_bpm=72, respiratory_rate=16, spo2_percent=98.0,
        consciousness=vitals_pb2.CONSCIOUSNESS_VOICE,
    )
    s.measured_at.FromDatetime(datetime(2026, 7, 1, 12, 0, tzinfo=UTC))

    dto = sample_to_dto(s)

    assert dto.device_id == "d1"
    assert dto.heart_rate_bpm == 72
    assert dto.respiratory_rate == 16
    assert dto.spo2_percent == 98.0
    assert dto.consciousness is Consciousness.VOICE


def test_unset_optionals_are_none_not_zero() -> None:
    # A single-purpose device: only SpO2 present; the rest must map to None,
    # not 0 (proto3 optional presence).
    s = vitals_pb2.VitalsSample(care_recipient_id="1", spo2_percent=95.0)
    s.measured_at.FromDatetime(datetime(2026, 7, 1, 12, 0, tzinfo=UTC))

    dto = sample_to_dto(s)

    assert dto.spo2_percent == 95.0
    assert dto.heart_rate_bpm is None
    assert dto.respiratory_rate is None
    assert dto.bp_systolic is None


def test_unspecified_consciousness_maps_to_none() -> None:
    s = vitals_pb2.VitalsSample(care_recipient_id="1")  # consciousness defaults UNSPECIFIED
    s.measured_at.FromDatetime(datetime(2026, 7, 1, 12, 0, tzinfo=UTC))
    assert sample_to_dto(s).consciousness is None
