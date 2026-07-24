"""HTTP surface for the media service (upload intake + hybrid search).

Kept thin: parse/validate the request, authorize, delegate to ``MediaService``,
shape the response. ``get_service``/``get_checker`` are the injection seams —
tests override them with fakes; production lazily builds the real ones.

Authorization (``AUTH_MODE=jwt``): the caller's ZITADEL bearer is verified against
the JWKS, then OpenFGA gates the care recipient — reads need ``viewer``, writes
``editor`` (mirrors telemetry). ``AUTH_MODE=disabled`` (dev default) bypasses both
and warns loudly at startup, so ``make dev-media`` runs without identity wiring.
"""

from __future__ import annotations

import io
import logging
import uuid as uuidlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from .auth import InvalidToken, verify_subject
from .authz import RELATION_READ, RELATION_WRITE
from .config import Settings
from .domain.models import MediaAsset, MediaKind
from .ports import AccessChecker, SearchHit
from .service import MediaService

log = logging.getLogger("media.api")

_CHUNK = 1024 * 1024


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if Settings().auth_mode != "jwt":
        log.warning(
            "AUTH_MODE=%s — media authorization DISABLED (dev/demo only); every "
            "authenticated request is allowed for any care recipient",
            Settings().auth_mode,
        )
    yield


app = FastAPI(title="MaagapAruga Media", version="0.1.0", lifespan=_lifespan)

_service: MediaService | None = None
_checker: AccessChecker | None = None


def get_service() -> MediaService:
    """Return the process-wide service, building it on first use."""
    global _service
    if _service is None:
        from .wiring import build_service

        _service = build_service()
    return _service


def get_settings() -> Settings:
    return Settings()


def get_checker() -> AccessChecker:
    global _checker
    if _checker is None:
        from .authz import OpenFgaChecker

        _checker = OpenFgaChecker()
    return _checker


ServiceDep = Annotated[MediaService, Depends(get_service)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CheckerDep = Annotated[AccessChecker, Depends(get_checker)]


async def caller_subject(request: Request, settings: SettingsDep) -> str | None:
    """The verified caller id, or None when authorization is disabled (dev)."""
    if settings.auth_mode != "jwt":
        return None
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        return verify_subject(token, settings)
    except InvalidToken:
        raise HTTPException(status_code=401, detail="invalid token") from None


CallerDep = Annotated["str | None", Depends(caller_subject)]


def _authorized(
    sub: str | None, relation: str, recipient_id: int, checker: AccessChecker, settings: Settings
) -> bool:
    if settings.auth_mode != "jwt":
        return True
    return sub is not None and checker.allowed(sub, relation, recipient_id)


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
    settings: SettingsDep,
    checker: CheckerDep,
    caller: CallerDep,
    care_recipient_id: Annotated[int, Form(ge=1)],
    kind: Annotated[MediaKind, Form()],
    file: Annotated[UploadFile, File()],
) -> AssetOut:
    if not _authorized(caller, RELATION_WRITE, care_recipient_id, checker, settings):
        raise HTTPException(status_code=403, detail="not authorized for this care recipient")

    # Stream the body with a running cap so the size limit bounds memory instead
    # of only rejecting after the whole file is already resident.
    buf = io.BytesIO()
    total = 0
    while chunk := await file.read(_CHUNK):
        total += len(chunk)
        if total > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"file exceeds {settings.max_upload_bytes} bytes; "
                "use a presigned PUT for large media",
            )
        buf.write(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="empty upload")
    buf.seek(0)

    asset = await svc.intake(
        care_recipient_id=care_recipient_id,
        kind=kind,
        filename=file.filename or "upload.bin",
        content_type=file.content_type or "application/octet-stream",
        body=buf,
        size_bytes=total,
    )
    return AssetOut.of(asset)


@app.get("/media/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: str,
    svc: ServiceDep,
    settings: SettingsDep,
    checker: CheckerDep,
    caller: CallerDep,
) -> AssetOut:
    try:
        uuidlib.UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="asset not found") from None
    asset = await svc.get(asset_id)
    # 404 for both missing and unauthorized — don't reveal an asset's existence
    # to a caller with no relationship to its care recipient.
    if asset is None or not _authorized(
        caller, RELATION_READ, asset.care_recipient_id, checker, settings
    ):
        raise HTTPException(status_code=404, detail="asset not found")
    return AssetOut.of(asset)


@app.get("/search", response_model=SearchOut)
async def search(
    svc: ServiceDep,
    settings: SettingsDep,
    checker: CheckerDep,
    caller: CallerDep,
    q: Annotated[str, Query(min_length=1)],
    care_recipient_id: Annotated[int, Query(ge=1)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SearchOut:
    # care_recipient_id is REQUIRED and authorized — a caller can only search
    # transcripts for a recipient they may view (never "everyone's").
    if not _authorized(caller, RELATION_READ, care_recipient_id, checker, settings):
        raise HTTPException(status_code=403, detail="not authorized for this care recipient")
    hits = await svc.search(q, care_recipient_id=care_recipient_id, limit=limit)
    return SearchOut(query=q, hits=[HitOut.of(h) for h in hits])
