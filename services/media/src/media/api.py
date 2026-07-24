"""HTTP surface for the media service (upload intake + hybrid search).

Kept thin: parse/validate the request, delegate to ``MediaService``, shape the
response. ``get_service`` is the injection seam — tests override it with a
service wired to fakes; production lazily builds the real one via ``wiring``.
"""

from __future__ import annotations

import io
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from .config import Settings
from .domain.models import MediaAsset, MediaKind
from .ports import SearchHit
from .service import MediaService

app = FastAPI(title="MaagapAruga Media", version="0.1.0")

_service: MediaService | None = None


def get_service() -> MediaService:
    """Return the process-wide service, building it on first use."""
    global _service
    if _service is None:
        from .wiring import build_service

        _service = build_service()
    return _service


# Depends()/File()/Form() live in Annotated aliases (evaluated once at import),
# the modern FastAPI style — no function calls in argument defaults.
ServiceDep = Annotated[MediaService, Depends(get_service)]


class AssetOut(BaseModel):
    id: str
    care_recipient_id: int
    kind: MediaKind
    filename: str
    content_type: str
    size_bytes: int
    status: str

    @classmethod
    def of(cls, a: MediaAsset) -> AssetOut:
        return cls(
            id=a.id,
            care_recipient_id=a.care_recipient_id,
            kind=a.kind,
            filename=a.filename,
            content_type=a.content_type,
            size_bytes=a.size_bytes,
            status=a.status,
        )


class HitOut(BaseModel):
    asset_id: str
    care_recipient_id: int
    index: int
    start_ms: int
    end_ms: int
    text: str
    score: float

    @classmethod
    def of(cls, h: SearchHit) -> HitOut:
        return cls(
            asset_id=h.asset_id,
            care_recipient_id=h.care_recipient_id,
            index=h.index,
            start_ms=h.start_ms,
            end_ms=h.end_ms,
            text=h.text,
            score=h.score,
        )


class SearchOut(BaseModel):
    query: str
    hits: list[HitOut]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/media", response_model=AssetOut, status_code=201)
async def upload(
    svc: ServiceDep,
    care_recipient_id: Annotated[int, Form(ge=1)],
    kind: Annotated[MediaKind, Form()],
    file: Annotated[UploadFile, File()],
) -> AssetOut:
    max_bytes = Settings().max_upload_bytes
    data = await file.read()
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"file exceeds {max_bytes} bytes; use a presigned PUT for large media",
        )
    if not data:
        raise HTTPException(status_code=400, detail="empty upload")

    asset = await svc.intake(
        care_recipient_id=care_recipient_id,
        kind=kind,
        filename=file.filename or "upload.bin",
        content_type=file.content_type or "application/octet-stream",
        body=io.BytesIO(data),
        size_bytes=len(data),
    )
    return AssetOut.of(asset)


@app.get("/media/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: str, svc: ServiceDep) -> AssetOut:
    asset = await svc.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return AssetOut.of(asset)


@app.get("/search", response_model=SearchOut)
async def search(
    svc: ServiceDep,
    q: Annotated[str, Query(min_length=1)],
    care_recipient_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SearchOut:
    hits = await svc.search(q, care_recipient_id=care_recipient_id, limit=limit)
    return SearchOut(query=q, hits=[HitOut.of(h) for h in hits])
