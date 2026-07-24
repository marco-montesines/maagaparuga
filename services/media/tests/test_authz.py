"""Authorization behaviour with AUTH_MODE=jwt (caller_subject overridden so the
tests need no real ZITADEL token; the OpenFGA check is a fake)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from media.api import app, caller_subject, get_checker, get_service
from media.authz import RELATION_READ, RELATION_WRITE
from media.domain.models import AssetStatus, MediaAsset, MediaKind
from media.ports import SearchHit
from media.service import MediaService
from tests.fakes import (
    FakeCatalog,
    FakeChecker,
    FakeEmbedder,
    FakeIndex,
    FakeObjectStore,
    FakeQueue,
)

CALLER = "user-123"


def _seed_asset(catalog: FakeCatalog, recipient: int) -> str:
    asset_id = str(uuid.uuid4())
    catalog.create(
        MediaAsset(
            id=asset_id,
            care_recipient_id=recipient,
            kind=MediaKind.TELECONSULT,
            filename="c.wav",
            content_type="audio/wav",
            size_bytes=10,
            object_key=f"{recipient}/{asset_id}/c.wav",
            status=AssetStatus.INDEXED,
        )
    )
    return asset_id


@pytest.fixture
def make_client(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("AUTH_MODE", "jwt")

    def _make(checker: FakeChecker) -> tuple[TestClient, FakeCatalog]:
        catalog = FakeCatalog()
        index = FakeIndex(
            hits=[
                SearchHit(
                    asset_id="a1",
                    care_recipient_id=1,
                    index=0,
                    start_ms=0,
                    end_ms=10,
                    text="x",
                    score=1.0,
                )
            ]
        )
        svc = MediaService(
            store=FakeObjectStore(),
            catalog=catalog,
            queue=FakeQueue(),
            index=index,
            embedder=FakeEmbedder(),
        )
        app.dependency_overrides[get_service] = lambda: svc
        app.dependency_overrides[get_checker] = lambda: checker
        app.dependency_overrides[caller_subject] = lambda: CALLER
        return TestClient(app), catalog

    yield _make
    app.dependency_overrides.clear()


def test_upload_requires_editor(make_client) -> None:  # type: ignore[no-untyped-def]
    client, _ = make_client(FakeChecker(default=False))
    resp = client.post(
        "/media",
        data={"care_recipient_id": "1", "kind": "teleconsult"},
        files={"file": ("v.wav", b"bytes", "audio/wav")},
    )
    assert resp.status_code == 403


def test_upload_allowed_with_editor(make_client) -> None:  # type: ignore[no-untyped-def]
    client, _ = make_client(FakeChecker(allowed={(CALLER, RELATION_WRITE, 1)}))
    resp = client.post(
        "/media",
        data={"care_recipient_id": "1", "kind": "teleconsult"},
        files={"file": ("v.wav", b"bytes", "audio/wav")},
    )
    assert resp.status_code == 201


def test_get_asset_hidden_without_viewer(make_client) -> None:  # type: ignore[no-untyped-def]
    client, catalog = make_client(FakeChecker(default=False))
    asset_id = _seed_asset(catalog, recipient=1)
    # unauthorized -> 404 (existence hidden), not 403
    assert client.get(f"/media/{asset_id}").status_code == 404


def test_get_asset_allowed_with_viewer(make_client) -> None:  # type: ignore[no-untyped-def]
    client, catalog = make_client(FakeChecker(allowed={(CALLER, RELATION_READ, 1)}))
    asset_id = _seed_asset(catalog, recipient=1)
    resp = client.get(f"/media/{asset_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == asset_id


def test_search_requires_viewer(make_client) -> None:  # type: ignore[no-untyped-def]
    client, _ = make_client(FakeChecker(default=False))
    assert client.get("/search", params={"q": "x", "care_recipient_id": 1}).status_code == 403


def test_search_allowed_with_viewer(make_client) -> None:  # type: ignore[no-untyped-def]
    client, _ = make_client(FakeChecker(allowed={(CALLER, RELATION_READ, 1)}))
    resp = client.get("/search", params={"q": "x", "care_recipient_id": 1})
    assert resp.status_code == 200
    assert len(resp.json()["hits"]) == 1


def test_search_requires_recipient_param(make_client) -> None:  # type: ignore[no-untyped-def]
    client, _ = make_client(FakeChecker(default=True))
    # omitting care_recipient_id -> 422 (no more "search everyone")
    assert client.get("/search", params={"q": "x"}).status_code == 422


def test_missing_bearer_is_401(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # caller_subject NOT overridden: real dependency runs, AUTH_MODE=jwt, no header
    monkeypatch.setenv("AUTH_MODE", "jwt")
    app.dependency_overrides[get_service] = lambda: MediaService(
        store=FakeObjectStore(),
        catalog=FakeCatalog(),
        queue=FakeQueue(),
        index=FakeIndex(),
        embedder=FakeEmbedder(),
    )
    app.dependency_overrides[get_checker] = lambda: FakeChecker(default=True)
    try:
        with TestClient(app) as client:
            resp = client.get("/search", params={"q": "x", "care_recipient_id": 1})
            assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
