"""Runtime configuration (environment-driven, pydantic-settings).

Field names map to upper-case env vars (``s3_endpoint`` -> ``S3_ENDPOINT``).
Names align with the platform's other services where they overlap.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # PostgreSQL — the media catalog (media_assets).
    db_host: str = "maagaparuga-pg-rw"
    db_port: int = 5432
    db_name: str = "app"
    db_user: str = "app"
    db_password: str = ""

    # Object store (SeaweedFS S3, claim-check binaries).
    s3_endpoint: str = "http://seaweedfs:8333"
    s3_bucket: str = "media"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"  # SeaweedFS ignores it; boto3 requires one

    # NATS JetStream (job queue).
    nats_url: str = "nats://nats:4222"

    # OpenSearch (hybrid search index).
    opensearch_url: str = "http://opensearch:9200"
    opensearch_user: str = ""       # dev runs security-disabled; empty = no auth
    opensearch_password: str = ""
    opensearch_index: str = "media_segments"

    # Worker ML models (CPU, int8).
    whisper_model: str = "base"           # tiny|base|small (int8 CPU)
    whisper_compute_type: str = "int8"
    whisper_cache_dir: str = "/models"    # PVC on-cluster; weights persist restarts
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dims: int = 384

    # Worker liveness endpoint (the Deployment is otherwise port-less).
    health_addr: str = ":9091"

    # Simulator: where the media intake API lives (for synthetic uploads).
    media_api_url: str = "http://media:8000"

    # Upload guard: multipart size cap (bytes) before requiring a presigned PUT.
    max_upload_bytes: int = 50 * 1024 * 1024

    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password}"
        )
