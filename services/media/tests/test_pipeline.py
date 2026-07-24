from __future__ import annotations

import io
from pathlib import Path

from media.domain.models import AssetStatus, MediaAsset, MediaKind, ProcessingJob
from media.pipeline import TranscriptionPipeline
from tests.fakes import FakeCatalog, FakeEmbedder, FakeIndex, FakeObjectStore, FakeTranscriber


def _noop_normalize(src: str, dst: str) -> None:
    # The fake transcriber ignores the path; just produce an empty wav file.
    Path(dst).write_bytes(b"")


def _seed(store: FakeObjectStore, catalog: FakeCatalog, key: str, asset_id: str) -> None:
    store.put(key, io.BytesIO(b"raw-media-bytes"), "audio/wav")
    catalog.create(
        MediaAsset(
            id=asset_id,
            care_recipient_id=1,
            kind=MediaKind.TELECONSULT,
            filename="c.wav",
            content_type="audio/wav",
            size_bytes=15,
            object_key=key,
            status=AssetStatus.UPLOADED,
        )
    )


def _pipeline(store, catalog, transcriber, index, embedder):  # type: ignore[no-untyped-def]
    # normalize is a no-op copy: the fake transcriber ignores the path anyway.
    return TranscriptionPipeline(
        store=store,
        catalog=catalog,
        transcriber=transcriber,
        embedder=embedder,
        index=index,
        normalize=_noop_normalize,
    )


def test_pipeline_transcribes_embeds_indexes_and_marks_done() -> None:
    store, catalog, index, embedder = (
        FakeObjectStore(), FakeCatalog(), FakeIndex(), FakeEmbedder()
    )
    transcriber = FakeTranscriber(
        spans=[(0, 1500, "shortness of breath"), (1500, 3000, "blood pressure stable")]
    )
    _seed(store, catalog, "1/a1/c.wav", "a1")
    job = ProcessingJob(
        asset_id="a1", care_recipient_id=1, kind=MediaKind.TELECONSULT, object_key="1/a1/c.wav"
    )

    count = _pipeline(store, catalog, transcriber, index, embedder).process(job)

    assert count == 2
    assert len(index.indexed) == 2
    assert index.indexed[0].text == "shortness of breath"
    assert index.indexed[1].index == 1
    assert catalog.assets["a1"].status is AssetStatus.INDEXED


def test_pipeline_with_no_speech_marks_indexed_without_writing() -> None:
    store, catalog, index, embedder = (
        FakeObjectStore(), FakeCatalog(), FakeIndex(), FakeEmbedder()
    )
    transcriber = FakeTranscriber(spans=[])
    _seed(store, catalog, "1/a2/c.wav", "a2")
    job = ProcessingJob(
        asset_id="a2", care_recipient_id=1, kind=MediaKind.TELECONSULT, object_key="1/a2/c.wav"
    )

    count = _pipeline(store, catalog, transcriber, index, embedder).process(job)

    assert count == 0
    assert index.indexed == []
    assert catalog.assets["a2"].status is AssetStatus.INDEXED
