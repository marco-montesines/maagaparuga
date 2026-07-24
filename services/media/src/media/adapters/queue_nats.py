"""NATS JetStream job queue (claim-check messages).

Mirrors the telemetry broker's conventions: a WorkQueue stream (acked jobs leave
the stream), file storage, a durable pull consumer. The API publishes; the
worker (increment 2) consumes. nats-py is imported lazily.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from ..config import Settings
from ..domain.models import MediaKind, ProcessingJob

STREAM_NAME = "MEDIA"
SUBJECT_JOB = "media.jobs"
SUBJECT_DEAD = "media.dead"
CONSUMER_NAME = "media-worker"


def encode_job(job: ProcessingJob) -> bytes:
    return json.dumps(
        {
            "asset_id": job.asset_id,
            "care_recipient_id": job.care_recipient_id,
            "kind": job.kind.value,
            "object_key": job.object_key,
        }
    ).encode()


def decode_job(payload: bytes) -> ProcessingJob:
    d = json.loads(payload)
    return ProcessingJob(
        asset_id=d["asset_id"],
        care_recipient_id=d["care_recipient_id"],
        kind=MediaKind(d["kind"]),
        object_key=d["object_key"],
    )


class NatsJobQueue:
    """Publisher side of the media job stream (async)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._url = (settings or Settings()).nats_url
        self._nc: Any | None = None
        self._js: Any | None = None
        self._lock = asyncio.Lock()

    async def _ensure(self) -> Any:
        # Fast path once connected; the lock serializes the first-use connect so
        # two concurrent uploads don't each open (and leak) a NATS connection.
        if self._js is not None:
            return self._js
        async with self._lock:
            if self._js is None:
                import nats

                nc = await nats.connect(self._url)
                js = nc.jetstream()
                # Idempotent: every replica can create-or-update at startup.
                await js.add_stream(
                    name=STREAM_NAME,
                    subjects=[SUBJECT_JOB, SUBJECT_DEAD],
                    retention="workqueue",
                    storage="file",
                )
                self._nc, self._js = nc, js
        return self._js

    async def publish(self, job: ProcessingJob) -> None:
        js = await self._ensure()
        await js.publish(SUBJECT_JOB, encode_job(job))

    async def close(self) -> None:
        if self._nc is not None:
            await self._nc.close()
            self._nc = None
            self._js = None
