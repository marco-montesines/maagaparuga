"""In-memory fakes for the ports — the fast suite never touches S3/NATS/torch."""

from __future__ import annotations

from typing import BinaryIO

from media.domain.models import AssetStatus, MediaAsset, ProcessingJob, TranscriptSegment
from media.ports import SearchHit


class FakeObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, body: BinaryIO, content_type: str) -> None:
        self.objects[key] = body.read()

    def get(self, key: str) -> bytes:
        return self.objects[key]


class FakeCatalog:
    def __init__(self) -> None:
        self.assets: dict[str, MediaAsset] = {}

    def create(self, asset: MediaAsset) -> None:
        self.assets[asset.id] = asset

    def get(self, asset_id: str) -> MediaAsset | None:
        return self.assets.get(asset_id)

    def set_status(self, asset_id: str, status: AssetStatus) -> None:
        a = self.assets[asset_id]
        self.assets[asset_id] = MediaAsset(
            id=a.id,
            care_recipient_id=a.care_recipient_id,
            kind=a.kind,
            filename=a.filename,
            content_type=a.content_type,
            size_bytes=a.size_bytes,
            object_key=a.object_key,
            status=status,
            created_at=a.created_at,
        )


class FakeQueue:
    def __init__(self) -> None:
        self.published: list[ProcessingJob] = []

    async def publish(self, job: ProcessingJob) -> None:
        self.published.append(job)


class FakeIndex:
    def __init__(self, hits: list[SearchHit] | None = None) -> None:
        self.hits = hits or []
        self.indexed: list[TranscriptSegment] = []

    def index_segments(
        self, segments: list[TranscriptSegment], vectors: list[list[float]]
    ) -> None:
        self.indexed.extend(segments)

    def search(
        self, query: str, vector: list[float], *, care_recipient_id: int | None, limit: int
    ) -> list[SearchHit]:
        hits = self.hits
        if care_recipient_id is not None:
            hits = [h for h in hits if h.care_recipient_id == care_recipient_id]
        return hits[:limit]


class FakeTranscriber:
    def __init__(self, spans: list[tuple[int, int, str]] | None = None) -> None:
        self.spans = spans or []
        self.calls: list[str] = []

    def transcribe(self, audio_path: str) -> list[tuple[int, int, str]]:
        self.calls.append(audio_path)
        return self.spans


class FakeEmbedder:
    def __init__(self, dims: int = 384) -> None:
        self._dims = dims

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self._dims for _ in texts]

    @property
    def dimensions(self) -> int:
        return self._dims
