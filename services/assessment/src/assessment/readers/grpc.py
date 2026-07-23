"""Telemetry gRPC vitals reader — calls VitalsService/GetWindow.

The strict-boundary reader: it depends only on the telemetry **proto contract**
(the generated stubs under ``assessment.gen``), not the ClickHouse schema. It
authenticates as the assessment service by presenting a bearer token in the gRPC
metadata, which telemetry verifies (JWKS) and authorises.

Provisioning the assessment service identity + its OpenFGA read grant is a
deployment step (like the device onboarding); the token arrives via config
(``TELEMETRY_TOKEN``). Select with ``VITALS_READER=grpc``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from ..domain.models import Consciousness
from ..gen.maagaparuga.telemetry.v1 import vitals_pb2, vitals_pb2_grpc
from ..ports import VitalsSampleDTO

_CONSCIOUSNESS = {
    vitals_pb2.CONSCIOUSNESS_ALERT: Consciousness.ALERT,
    vitals_pb2.CONSCIOUSNESS_VOICE: Consciousness.VOICE,
    vitals_pb2.CONSCIOUSNESS_PAIN: Consciousness.PAIN,
    vitals_pb2.CONSCIOUSNESS_UNRESPONSIVE: Consciousness.UNRESPONSIVE,
}


def _opt(sample: Any, field: str) -> Any:
    # proto3 `optional` scalars: HasField distinguishes "not measured" from 0.
    return getattr(sample, field) if sample.HasField(field) else None


def sample_to_dto(sample: Any) -> VitalsSampleDTO:
    """Map a telemetry VitalsSample onto the reader's DTO. Module-level so the
    mapping can be unit-tested without a live server."""
    return VitalsSampleDTO(
        measured_at=sample.measured_at.ToDatetime(),
        device_id=sample.device_id or None,
        heart_rate_bpm=_opt(sample, "heart_rate_bpm"),
        respiratory_rate=_opt(sample, "respiratory_rate"),
        spo2_percent=_opt(sample, "spo2_percent"),
        body_temp_c=_opt(sample, "body_temp_c"),
        bp_systolic=_opt(sample, "bp_systolic"),
        bp_diastolic=_opt(sample, "bp_diastolic"),
        consciousness=_CONSCIOUSNESS.get(sample.consciousness),
    )


class GrpcVitalsReader:
    def __init__(self, *, target: str, token: str) -> None:
        self._target = target
        self._metadata = (("authorization", f"Bearer {token}"),) if token else ()
        self._stub: Any = None

    def _connect(self) -> Any:
        if self._stub is None:
            # h2c in-cluster, same as the device simulator's transport.
            self._stub = vitals_pb2_grpc.VitalsServiceStub(grpc.insecure_channel(self._target))
        return self._stub

    def window(
        self, recipient_id: str, since: datetime, until: datetime, limit: int
    ) -> Sequence[VitalsSampleDTO]:
        request = vitals_pb2.GetWindowRequest(care_recipient_id=recipient_id, limit=limit)
        # `from` is a Python keyword, so the proto field is only reachable via
        # getattr; `to` is a normal attribute.
        _set_ts(getattr(request, "from"), since)
        _set_ts(request.to, until)

        response = self._connect().GetWindow(request, metadata=self._metadata)
        return [sample_to_dto(s) for s in response.samples]


def _set_ts(ts: Timestamp, value: datetime) -> None:
    ts.FromDatetime(value)
