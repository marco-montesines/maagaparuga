from __future__ import annotations

import asyncio
import io

import pytest

from media.domain.models import AssetStatus, MediaKind
from media.service import MediaService
from tests.fakes import FakeCatalog, FakeEmbedder, FakeIndex, FakeObjectStore, FakeQueue


def _service(queue: FakeQueue, catalog: FakeCatalog) -> MediaService:
    return MediaService(
        store=FakeObjectStore(),
        catalog=catalog,
        queue=queue,
        index=FakeIndex(),
        embedder=FakeEmbedder(),
    )


def test_intake_marks_failed_when_publish_fails() -> None:
    catalog = FakeCatalog()
    svc = _service(FakeQueue(fail=True), catalog)

    async def go() -> None:
        with pytest.raises(RuntimeError):
            await svc.intake(
                care_recipient_id=1,
                kind=MediaKind.TELECONSULT,
                filename="c.wav",
                content_type="audio/wav",
                body=io.BytesIO(b"bytes"),
                size_bytes=5,
            )

    asyncio.run(go())
    # the row exists but is FAILED, not stuck UPLOADED
    (asset,) = catalog.assets.values()
    assert asset.status is AssetStatus.FAILED
