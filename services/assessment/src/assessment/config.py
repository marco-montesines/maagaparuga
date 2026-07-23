"""Runtime configuration (environment-driven, pydantic-settings).

Field names map to upper-case env vars (``window_minutes`` -> ``WINDOW_MINUTES``).
Names align with the platform's telemetry-config where they overlap.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # PostgreSQL — questionnaire_responses (read) + assessment_results/alerts (write).
    db_host: str = "maagaparuga-pg-rw"
    db_port: int = 5432
    db_name: str = "app"
    db_user: str = "app"
    db_password: str = ""

    # Which VitalsReader adapter to use: "clickhouse" (direct read-only query) or
    # "grpc" (telemetry GetWindow). Both are supported; this selects the wiring.
    vitals_reader: str = "clickhouse"

    # ClickHouse reader (direct, read-only). clickhouse-connect speaks HTTP.
    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_db: str = "maagaparuga"
    clickhouse_user: str = "assessment"
    clickhouse_password: str = ""

    # gRPC reader (telemetry). Token is a bearer for the assessment service
    # identity; injected at runtime, never committed.
    telemetry_grpc: str = "telemetry:9090"
    telemetry_token: str = ""

    # Scoring window: how far back to look for a vitals snapshot, and the cap on
    # samples pulled.
    window_minutes: int = 60
    window_limit: int = 500

    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password}"
        )
