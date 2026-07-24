"""Application service: upload intake and hybrid search.

Thin orchestration over the ports. Blocking adapters (S3, PostgreSQL) are run in
a worker thread so they never stall the event loop; the job queue is natively
async. The worker's transcription pipeline lives separately (``pipeline``).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import BinaryIO

from .domain.models import AssetStatus, MediaAsset, MediaKind, ProcessingJob
from .ports import Catalog, Embedder, JobQueue, ObjectStore, SearchHit, TranscriptIndex


class MediaService:
    def __init__(
        self,
        *,
        store: ObjectStore,
        catalog: Catalog,
        queue: JobQueue,
        index: TranscriptIndex,
        embedder: Embedder,
    ) -> None:
        self._store = store
        self._catalog = catalog
        self._queue = queue
        self._index = index
        self._embedder = embedder

    async def intake(
        self,
        *,
        care_recipient_id: int,
        kind: MediaKind,
        filename: str,
        content_type: str,
        body: BinaryIO,
        size_bytes: int,
    ) -> MediaAsset:
        """Store the binary (claim-check), catalog it, and queue a job.

        Imaging kinds have no audio track, so they are catalogued as ``SKIPPED``
        and never queued — only recorded consultations produce a transcript.
        """
        asset_id = str(uuid.uuid4())
        object_key = f"{care_recipient_id}/{asset_id}/{filename}"

        await asyncio.to_thread(self._store.put, object_key, body, content_type)

        transcribe = kind.has_audio
        asset = MediaAsset(
            id=asset_id,
            care_recipient_id=care_recipient_id,
            kind=kind,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            object_key=object_key,
            status=AssetStatus.UPLOADED if transcribe else AssetStatus.SKIPPED,
        )
        await asyncio.to_thread(self._catalog.create, asset)

        if transcribe:
            await self._queue.publish(
                ProcessingJob(
                    asset_id=asset_id,
                    care_recipient_id=care_recipient_id,
                    kind=kind,
                    object_key=object_key,
                )
            )
        return asset

    async def get(self, asset_id: str) -> MediaAsset | None:
        return await asyncio.to_thread(self._catalog.get, asset_id)

    async def search(
        self, query: str, *, care_recipient_id: int | None, limit: int
    ) -> list[SearchHit]:
        """Hybrid (BM25 + k-NN) search: embed the query, then rank in OpenSearch."""
        vector = (await asyncio.to_thread(self._embedder.embed, [query]))[0]
        return await asyncio.to_thread(
            self._index.search,
            query,
            vector,
            care_recipient_id=care_recipient_id,
            limit=limit,
        )
