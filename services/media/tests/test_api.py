from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from media.api import app, get_service
from media.ports import SearchHit
from media.service import MediaService
from tests.fakes import FakeCatalog, FakeEmbedder, FakeIndex, FakeObjectStore, FakeQueue


@pytest.fixture
def ctx() -> Iterator[tuple[TestClient, FakeObjectStore, FakeCatalog, FakeQueue]]:
    store, catalog, queue = FakeObjectStore(), FakeCatalog(), FakeQueue()
    index = FakeIndex(
        hits=[
            SearchHit(
                asset_id="a1",
                care_recipient_id=1,
                index=0,
                start_ms=0,
                end_ms=2000,
                text="blood pressure looks stable",
                score=1.4,
            )
        ]
    )
    svc = MediaService(
        store=store, catalog=catalog, queue=queue, index=index, embedder=FakeEmbedder()
    )
    app.dependency_overrides[get_service] = lambda: svc
    with TestClient(app) as client:
        yield client, store, catalog, queue
    app.dependency_overrides.clear()


def test_teleconsult_upload_stores_and_queues(ctx) -> None:  # type: ignore[no-untyped-def]
    client, store, catalog, queue = ctx
    resp = client.post(
        "/media",
        data={"care_recipient_id": "1", "kind": "teleconsult"},
        files={"file": ("visit.mp4", b"fake-audio-bytes", "video/mp4")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "uploaded"
    assert body["kind"] == "teleconsult"
    # binary landed in the store, catalog row written, one job queued
    assert len(store.objects) == 1
    assert body["id"] in catalog.assets
    assert len(queue.published) == 1
    assert queue.published[0].kind.value == "teleconsult"


def test_imaging_upload_is_skipped_not_queued(ctx) -> None:  # type: ignore[no-untyped-def]
    client, _store, _catalog, queue = ctx
    resp = client.post(
        "/media",
        data={"care_recipient_id": "2", "kind": "xray"},
        files={"file": ("chest.dcm", b"fake-image", "application/dicom")},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "skipped"
    assert len(queue.published) == 0  # imaging has no audio to transcribe


def test_empty_upload_rejected(ctx) -> None:  # type: ignore[no-untyped-def]
    client, *_ = ctx
    resp = client.post(
        "/media",
        data={"care_recipient_id": "1", "kind": "teleconsult"},
        files={"file": ("empty.mp4", b"", "video/mp4")},
    )
    assert resp.status_code == 400


def test_oversize_upload_rejected(ctx, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client, *_ = ctx
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "4")
    resp = client.post(
        "/media",
        data={"care_recipient_id": "1", "kind": "teleconsult"},
        files={"file": ("big.mp4", b"more-than-four", "video/mp4")},
    )
    assert resp.status_code == 413


def test_get_asset_roundtrip_and_404(ctx) -> None:  # type: ignore[no-untyped-def]
    client, *_ = ctx
    created = client.post(
        "/media",
        data={"care_recipient_id": "1", "kind": "teleconsult"},
        files={"file": ("visit.mp4", b"bytes", "video/mp4")},
    ).json()
    got = client.get(f"/media/{created['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == created["id"]
    assert client.get("/media/does-not-exist").status_code == 404


def test_search_returns_hits(ctx) -> None:  # type: ignore[no-untyped-def]
    client, *_ = ctx
    resp = client.get("/search", params={"q": "blood pressure", "care_recipient_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "blood pressure"
    assert len(body["hits"]) == 1
    assert body["hits"][0]["start_ms"] == 0


def test_search_filters_by_recipient(ctx) -> None:  # type: ignore[no-untyped-def]
    client, *_ = ctx
    resp = client.get("/search", params={"q": "anything", "care_recipient_id": 999})
    assert resp.status_code == 200
    assert resp.json()["hits"] == []


def test_healthz(ctx) -> None:  # type: ignore[no-untyped-def]
    client, *_ = ctx
    assert client.get("/healthz").json() == {"status": "ok"}
