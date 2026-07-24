"""CLI entrypoint: one image, three roles (``api`` | ``worker`` | ``simulate``).

The deployment runs ``media api`` (intake + search) and ``media-worker`` runs
``media worker`` (JetStream consumer); ``simulate`` seeds synthetic mock media.
"""

from __future__ import annotations

import sys


def _run_api() -> None:
    import uvicorn

    uvicorn.run("media.api:app", host="0.0.0.0", port=8000)


def _run_worker() -> None:
    import asyncio

    from .worker import run

    asyncio.run(run())


def _run_simulate(argv: list[str]) -> None:
    from .simulator import main as sim_main

    sim_main(argv)


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        sys.exit("usage: media <api|worker|simulate> [options]")
    cmd, rest = argv[0], argv[1:]
    if cmd == "api":
        _run_api()
    elif cmd == "worker":
        _run_worker()
    elif cmd == "simulate":
        _run_simulate(rest)
    else:
        sys.exit(f"unknown command: {cmd!r} (expected api|worker|simulate)")


if __name__ == "__main__":
    main()
