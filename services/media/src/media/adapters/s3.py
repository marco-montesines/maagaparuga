"""S3 object-store adapter (SeaweedFS in dev; any S3 in cloud overlays).

The claim-check store: uploads land here, jobs carry only the key, the worker
fetches the binary back. boto3 is imported lazily so the module is cheap to load
and easy to fake in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, BinaryIO

from ..config import Settings

if TYPE_CHECKING:
    from ..config import Settings as _Settings


class S3ObjectStore:
    def __init__(self, settings: _Settings | None = None) -> None:
        self._s = settings or Settings()
        self._bucket = self._s.s3_bucket
        self._client: Any | None = None

    def _c(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                endpoint_url=self._s.s3_endpoint,
                aws_access_key_id=self._s.s3_access_key,
                aws_secret_access_key=self._s.s3_secret_key,
                region_name=self._s.s3_region,
            )
        return self._client

    def put(self, key: str, body: BinaryIO, content_type: str) -> None:
        self._c().put_object(
            Bucket=self._bucket, Key=key, Body=body, ContentType=content_type
        )

    def get(self, key: str) -> bytes:
        resp = self._c().get_object(Bucket=self._bucket, Key=key)
        data: bytes = resp["Body"].read()
        return data
