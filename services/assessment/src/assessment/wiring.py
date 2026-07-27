"""Production wiring: build the AssessmentService from Settings, selecting the
configured vitals reader. Concrete adapters (and their drivers) are imported
lazily here so nothing else in the service depends on them."""

from __future__ import annotations

from .config import Settings
from .ports import AssessmentStore, VitalsReader
from .service import AssessmentService


def build_service(settings: Settings | None = None) -> AssessmentService:
    settings = settings or Settings()
    return AssessmentService(
        _reader(settings),
        _store(settings),
        window_minutes=settings.window_minutes,
        window_limit=settings.window_limit,
    )


def _reader(settings: Settings) -> VitalsReader:
    if settings.vitals_reader == "clickhouse":
        from .readers.clickhouse import ClickHouseVitalsReader

        return ClickHouseVitalsReader(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            database=settings.clickhouse_db,
            user=settings.clickhouse_user,
            password=settings.clickhouse_password,
        )
    if settings.vitals_reader == "grpc":
        from .readers.grpc import GrpcVitalsReader

        return GrpcVitalsReader(target=settings.telemetry_grpc, token=settings.telemetry_token)
    raise ValueError(
        f"unknown VITALS_READER {settings.vitals_reader!r} (want 'clickhouse' or 'grpc')"
    )


def _store(settings: Settings) -> AssessmentStore:
    from .persistence.postgres import PgRepository

    return PgRepository(settings.dsn())
