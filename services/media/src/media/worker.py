"""Media worker: durable JetStream consumer driving the transcription pipeline.

Pulls jobs from the ``MEDIA`` stream, runs the (blocking) pipeline in a thread so
the event loop keeps draining, acks on success and naks on failure (JetStream
redelivers up to the consumer's max-deliver, then parks the message). A tiny
health server gives the port-less Deployment a liveness signal — a stalled
consumer that stops draining but stays up is a real failure a probe must catch
(same rationale as telemetry-writer).
"""

from __future__ import annotations

import asyncio
import logging
import signal
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from .adapters.queue_nats import CONSUMER_NAME, STREAM_NAME, SUBJECT_JOB, decode_job
from .config import Settings
from .pipeline import TranscriptionPipeline
from .wiring import build_pipeline

log = logging.getLogger("media.worker")

MAX_DELIVER = 5
FETCH_TIMEOUT = 5.0


class _Health(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_args: Any) -> None:  # silence access logging
        pass


def _serve_health(addr: str) -> None:
    host, _, port = addr.rpartition(":")
    server = HTTPServer((host or "0.0.0.0", int(port)), _Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("health server on %s", addr)


async def _consume(js: Any, pipeline: TranscriptionPipeline, stop: asyncio.Event) -> None:
    from nats.js.api import ConsumerConfig

    psub = await js.pull_subscribe(
        SUBJECT_JOB,
        durable=CONSUMER_NAME,
        config=ConsumerConfig(max_deliver=MAX_DELIVER, ack_wait=120),
    )
    log.info("consuming %s (durable=%s)", SUBJECT_JOB, CONSUMER_NAME)
    while not stop.is_set():
        try:
            msgs = await psub.fetch(1, timeout=FETCH_TIMEOUT)
        except TimeoutError:
            continue
        except Exception:
            log.exception("fetch failed")
            continue
        for msg in msgs:
            await _handle(msg, pipeline)


async def _handle(msg: Any, pipeline: TranscriptionPipeline) -> None:
    try:
        job = decode_job(msg.data)
        count = await asyncio.to_thread(pipeline.process, job)
        await msg.ack()
        log.info("indexed %d segment(s) for asset %s", count, job.asset_id)
    except Exception:
        log.exception("job failed; naking for redelivery")
        await msg.nak()


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
    _serve_health(s.health_addr)

    nc = await _connect(s.nats_url)
    js = nc.jetstream()
    await js.add_stream(
        name=STREAM_NAME,
        subjects=[SUBJECT_JOB, "media.dead"],
        retention="workqueue",
        storage="file",
    )

    pipeline = build_pipeline(s)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    try:
        await _consume(js, pipeline, stop)
    finally:
        await nc.drain()
        log.info("worker stopped")
