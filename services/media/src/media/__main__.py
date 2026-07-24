"""CLI entrypoint: one image, three roles (``api`` | ``worker`` | ``simulate``).

The deployment runs ``media api`` (intake + search); ``media-worker`` will run
``media worker`` (JetStream consumer) and ``simulate`` seeds synthetic mock media
— both land with the transcription pipeline (P4b increment 2).
"""

from __future__ import annotations

import sys


def _run_api() -> None:
    import uvicorn

    uvicorn.run("media.api:app", host="0.0.0.0", port=8000)


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        sys.exit("usage: media <api|worker|simulate> [options]")
    cmd = argv[0]
    if cmd == "api":
        _run_api()
    elif cmd in {"worker", "simulate"}:
        sys.exit(f"'{cmd}' lands with the transcription pipeline (P4b increment 2)")
    else:
        sys.exit(f"unknown command: {cmd!r} (expected api|worker|simulate)")


if __name__ == "__main__":
    main()
