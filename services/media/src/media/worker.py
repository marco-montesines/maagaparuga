"""Media worker: durable JetStream consumer driving the transcription pipeline.

Pulls jobs from the ``MEDIA`` stream, runs the (blocking) pipeline in a thread so
the event loop keeps draining. A permanent failure (undecodable message) is
dead-lettered to ``media.dead`` and removed immediately; a transient failure is
naked with backoff and, after ``MAX_DELIVER`` attempts, dead-lettered too — so a
poison message never spins the loop or sits unacked forever.

The health server reflects real consumer progress (a heartbeat the consume loop
stamps every iteration), not a constant 200 — so a wedged pipeline that stops
draining but keeps the process up is caught by the liveness probe and restarted.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import threading
import time
from collections.abc import Awaitable, Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from .adapters.queue_nats import (
    CONSUMER_NAME,
    STREAM_NAME,
    SUBJECT_DEAD,
    SUBJECT_JOB,
    decode_job,
)
from .config import Settings
from .pipeline import TranscriptionPipeline
from .wiring import build_pipeline

log = logging.getLogger("media.worker")

MAX_DELIVER = 5
FETCH_TIMEOUT = 5.0
NAK_BACKOFF = 5.0
# A consume loop that hasn't made a pass in this long is wedged (well above the
# fetch timeout and any real job time on the small mock clips).
STALL_SECONDS = 180.0


class _Liveness:
    """A heartbeat the consume loop stamps; the health handler reads it."""

    def __init__(self) -> None:
        self._last = time.monotonic()

    def beat(self) -> None:
        self._last = time.monotonic()

    def healthy(self) -> bool:
        return (time.monotonic() - self._last) < STALL_SECONDS


def _serve_health(addr: str, live: _Liveness) -> None:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            ok = live.healthy()
            self.send_response(200 if ok else 503)
            self.end_headers()
            self.wfile.write(b"ok" if ok else b"stalled")

        def log_message(self, *_args: Any) -> None:  # silence access logging
            pass

    host, _, port = addr.rpartition(":")
    server = HTTPServer((host or "0.0.0.0", int(port)), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("health server on %s", addr)


def _num_delivered(msg: Any) -> int:
    try:
        return int(msg.metadata.num_delivered)
    except Exception:
        return 1


async def _consume(
    js: Any,
    pipeline: TranscriptionPipeline,
    live: _Liveness,
    dead: Callable[[bytes], Awaitable[None]],
    stop: asyncio.Event,
) -> None:
    from nats.js.api import ConsumerConfig

    psub = await js.pull_subscribe(
        SUBJECT_JOB,
        durable=CONSUMER_NAME,
        config=ConsumerConfig(max_deliver=MAX_DELIVER, ack_wait=120),
    )
    log.info("consuming %s (durable=%s)", SUBJECT_JOB, CONSUMER_NAME)
    while not stop.is_set():
        live.beat()  # each pass (incl. idle fetch timeouts) proves liveness
        try:
            msgs = await psub.fetch(1, timeout=FETCH_TIMEOUT)
        except TimeoutError:
            continue
        except Exception:  # keep the loop alive on transient fetch errors
            log.exception("fetch failed")
            continue
        for msg in msgs:
            await _handle(msg, pipeline, dead)


async def _handle(
    msg: Any, pipeline: TranscriptionPipeline, dead: Callable[[bytes], Awaitable[None]]
) -> None:
    try:
        job = decode_job(msg.data)
    except Exception:  # malformed payload — never decodable, don't retry
        log.exception("undecodable message; dead-lettering")
        await dead(msg.data)
        await msg.term()
        return
    try:
        count = await asyncio.to_thread(pipeline.process, job)
        await msg.ack()
        log.info("indexed %d segment(s) for asset %s", count, job.asset_id)
    except Exception:
        delivered = _num_delivered(msg)
        if delivered >= MAX_DELIVER:
            log.exception("job failed %dx; dead-lettering asset %s", delivered, job.asset_id)
            await dead(msg.data)
            await msg.term()
        else:
            log.warning(
                "job failed (delivery %d/%d); retrying with backoff", delivered, MAX_DELIVER
            )
            await msg.nak(delay=NAK_BACKOFF)


async def _connect(url: str, *, attempts: int = 30, wait: float = 2.0) -> Any:
    """Connect to NATS, tolerating it not being ready yet at cold start.

    k8s gives no ordering guarantee between the worker and NATS, so retry the
    initial connect quietly instead of crashing (or spewing a stack trace) when
    the broker is a few seconds behind. Once connected, nats-py handles reconnects.
    """
    import nats

    for attempt in range(1, attempts + 1):
        try:
            return await nats.connect(url, max_reconnect_attempts=-1)
        except Exception as exc:
            if attempt == attempts:
                raise
            log.warning("NATS not ready (%s); retry %d/%d", exc, attempt, attempts)
            await asyncio.sleep(wait)
    raise RuntimeError("unreachable")  # loop always returns or re-raises


async def run(settings: Settings | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    s = settings or Settings()
    live = _Liveness()
    _serve_health(s.health_addr, live)

    nc = await _connect(s.nats_url)
    js = nc.jetstream()
    await js.add_stream(
        name=STREAM_NAME,
        subjects=[SUBJECT_JOB, SUBJECT_DEAD],
        retention="workqueue",
        storage="file",
    )

    async def dead(payload: bytes) -> None:
        await js.publish(SUBJECT_DEAD, payload)

    pipeline = build_pipeline(s)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    try:
        await _consume(js, pipeline, live, dead, stop)
    finally:
        await nc.drain()
        log.info("worker stopped")
