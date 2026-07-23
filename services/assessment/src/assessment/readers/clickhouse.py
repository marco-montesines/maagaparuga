"""Direct ClickHouse vitals reader (read-only).

Telemetry owns the *write* path to ClickHouse (validated, batched ingest — the
only writer). This reader is a read-only analytical consumer, which ClickHouse
is designed for; it connects with a dedicated **read-only** user. The trade-off
vs. the gRPC reader: no proto stubs or service auth, but it depends on the vitals
table's column names (a read contract kept in step with the telemetry store).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from ..domain.models import Consciousness
from ..ports import VitalsSampleDTO

# consciousness is stored as the telemetry proto enum name, e.g. "CONSCIOUSNESS_ALERT".
_CONSCIOUSNESS = {
    "CONSCIOUSNESS_ALERT": Consciousness.ALERT,
    "CONSCIOUSNESS_VOICE": Consciousness.VOICE,
    "CONSCIOUSNESS_PAIN": Consciousness.PAIN,
    "CONSCIOUSNESS_UNRESPONSIVE": Consciousness.UNRESPONSIVE,
}

_QUERY = """
SELECT measured_at, device_id, heart_rate_bpm, respiratory_rate, spo2_percent,
       body_temp_c, bp_systolic, bp_diastolic, consciousness
FROM vitals
WHERE care_recipient_id = {rid:String}
  AND measured_at BETWEEN {since:DateTime64(3)} AND {until:DateTime64(3)}
ORDER BY measured_at DESC
LIMIT {limit:UInt32}
"""


def _consciousness(raw: str | None) -> Consciousness | None:
    return _CONSCIOUSNESS.get(raw) if raw else None


def _int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _float(value: Any) -> float | None:
    return float(value) if value is not None else None


class ClickHouseVitalsReader:
    """Reads vitals windows straight from ClickHouse. The client is created
    lazily on first use so constructing the reader (at startup) needs no live
    connection."""

    def __init__(
        self, *, host: str, port: int, database: str, user: str, password: str
    ) -> None:
        self._cfg = {
            "host": host, "port": port, "database": database,
            "username": user, "password": password,
        }
        self._client: Any = None

    def _connect(self) -> Any:
        if self._client is None:
            import clickhouse_connect

            self._client = clickhouse_connect.get_client(**self._cfg)
        return self._client

    def window(
        self, recipient_id: str, since: datetime, until: datetime, limit: int
    ) -> Sequence[VitalsSampleDTO]:
        result = self._connect().query(
            _QUERY,
            parameters={"rid": recipient_id, "since": since, "until": until, "limit": limit},
        )
        return [
            VitalsSampleDTO(
                measured_at=row[0],
                device_id=row[1] or None,
                heart_rate_bpm=_int(row[2]),
                respiratory_rate=_int(row[3]),
                spo2_percent=_float(row[4]),
                body_temp_c=_float(row[5]),
                bp_systolic=_int(row[6]),
                bp_diastolic=_int(row[7]),
                consciousness=_consciousness(row[8]),
            )
            for row in result.result_rows
        ]
