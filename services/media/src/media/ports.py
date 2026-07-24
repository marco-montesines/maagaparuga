"""Ports — the abstract seams the API and worker depend on.

Concrete adapters (S3, PostgreSQL, NATS, OpenSearch, faster-whisper, MiniLM)
implement these Protocols and are assembled in ``wiring``. Tests supply fakes,
so the fast suite never imports boto3/torch/etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Protocol, runtime_checkable

from .domain.models import AssetStatus, MediaAsset, ProcessingJob, TranscriptSegment


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One hybrid-search result, deep-linking into a media timestamp."""

    asset_id: str
    care_recipient_id: int
    index: int
    start_ms: int
    end_ms: int
    text: str
    score: float


@runtime_checkable
class ObjectStore(Protocol):
    """Claim-check binary store (S3-compatible)."""

    def put(self, key: str, body: BinaryIO, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...


@runtime_checkable
class Catalog(Protocol):
    """Media catalog (metadata rows; the binary lives in the ObjectStore)."""

    def create(self, asset: MediaAsset) -> None: ...

    def get(self, asset_id: str) -> MediaAsset | None: ...

    def set_status(self, asset_id: str, status: AssetStatus) -> None: ...


@runtime_checkable
class JobQueue(Protocol):
    """Durable job queue (JetStream) carrying claim-check messages."""

    async def publish(self, job: ProcessingJob) -> None: ...


@runtime_checkable
class TranscriptIndex(Protocol):
    """Full-text + vector index over transcript segments (OpenSearch)."""

    def index_segments(self, segments: list[TranscriptSegment], vectors: list[list[float]]) -> None:
        ...

    def search(
        self, query: str, vector: list[float], *, care_recipient_id: int | None, limit: int
    ) -> list[SearchHit]: ...


@runtime_checkable
class Transcriber(Protocol):
    """Speech-to-text over an audio file, yielding timestamped segments."""

    def transcribe(self, audio_path: str) -> list[tuple[int, int, str]]:
        """Return (start_ms, end_ms, text) tuples in order."""
        ...


@runtime_checkable
class Embedder(Protocol):
    """Sentence embeddings (query and segment text share one model)."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimensions(self) -> int: ...


@runtime_checkable
class AccessChecker(Protocol):
    """Relationship-based access check (OpenFGA): may ``user`` act as ``relation``
    on ``care_recipient:{recipient_id}``?"""

    def allowed(self, user_sub: str, relation: str, recipient_id: int) -> bool: ...
