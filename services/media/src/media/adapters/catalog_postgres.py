"""PostgreSQL media catalog (media_assets).

The table is owned by the web app's Laravel migrations (single schema owner);
this adapter only reads/writes rows. psycopg is imported lazily.
"""

from __future__ import annotations

from typing import Any

from ..config import Settings
from ..domain.models import AssetStatus, MediaAsset, MediaKind


class PgCatalog:
    def __init__(self, settings: Settings | None = None) -> None:
        self._dsn = (settings or Settings()).dsn()

    def _connect(self) -> Any:
        import psycopg

        return psycopg.connect(self._dsn)

    def create(self, asset: MediaAsset) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO media_assets
                    (id, care_recipient_id, kind, filename, content_type,
                     size_bytes, object_key, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), now())
                """,
                (
                    asset.id,
                    asset.care_recipient_id,
                    asset.kind.value,
                    asset.filename,
                    asset.content_type,
                    asset.size_bytes,
                    asset.object_key,
                    asset.status.value,
                ),
            )

    def get(self, asset_id: str) -> MediaAsset | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, care_recipient_id, kind, filename, content_type,
                       size_bytes, object_key, status, created_at
                FROM media_assets WHERE id = %s
                """,
                (asset_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return MediaAsset(
            id=row[0],
            care_recipient_id=row[1],
            kind=MediaKind(row[2]),
            filename=row[3],
            content_type=row[4],
            size_bytes=row[5],
            object_key=row[6],
            status=AssetStatus(row[7]),
            created_at=row[8],
        )

    def set_status(self, asset_id: str, status: AssetStatus) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE media_assets SET status = %s, updated_at = now() WHERE id = %s",
                (status.value, asset_id),
            )
