"""Core media-pipeline types — pure data, no I/O.

An *asset* is one uploaded mock media file (imaging or audio/video). Its binary
lives in the object store (claim-check); PostgreSQL holds only the catalog row.
A *job* is the small message published to JetStream — it carries the object key,
never the bytes. A *segment* is one timestamped transcript span the worker
produces and indexes for hybrid search.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class MediaKind(StrEnum):
    """Mock media categories (no real clinical media — data/mock only)."""

    XRAY = "xray"
    ULTRASOUND_2D = "ultrasound_2d"
    ULTRASOUND_3D = "ultrasound_3d"
    ULTRASOUND_4D = "ultrasound_4d"
    MRI = "mri"
    TELECONSULT = "teleconsult"  # recorded video/audio consultation

    @property
    def has_audio(self) -> bool:
        """Only recorded consultations carry an audio track to transcribe."""
        return self is MediaKind.TELECONSULT


class AssetStatus(StrEnum):
    """Lifecycle of an asset through the pipeline."""

    UPLOADED = "uploaded"      # binary stored, job queued
    PROCESSING = "processing"  # worker picked the job up
    INDEXED = "indexed"        # transcript segments written + searchable
    SKIPPED = "skipped"        # no audio track (imaging) — nothing to transcribe
    FAILED = "failed"          # processing error (dead-lettered)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class MediaAsset:
    """A catalogued mock media upload."""

    id: str                       # uuid string (catalog primary key)
    care_recipient_id: int
    kind: MediaKind
    filename: str
    content_type: str
    size_bytes: int
    object_key: str               # bucket-relative key in the object store
    status: AssetStatus = AssetStatus.UPLOADED
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class ProcessingJob:
    """Claim-check message: enough to fetch + process, never the binary."""

    asset_id: str
    care_recipient_id: int
    kind: MediaKind
    object_key: str


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """One timestamped span of a consultation transcript."""

    asset_id: str
    care_recipient_id: int
    index: int                    # 0-based order within the asset
    start_ms: int
    end_ms: int
    text: str

    @property
    def segment_id(self) -> str:
        """Stable OpenSearch document id (idempotent re-index)."""
        return f"{self.asset_id}:{self.index}"
