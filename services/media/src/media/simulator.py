"""Synthetic media generator — the companion to the vitals simulator.

Renders clearly-fictitious "consultation" narration to speech (espeak-ng) and
uploads it as teleconsult recordings, plus a couple of imaging placeholders, to
the intake API. No real media, ever — every sentence is invented demo text.
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from .config import Settings

# Invented, generic consultation lines — nothing real, nothing personal.
SENTENCES = [
    "The care recipient reports mild shortness of breath after climbing the stairs.",
    "Blood pressure and heart rate stayed stable throughout the visit today.",
    "We reviewed the evening medication schedule and lowered the dose slightly.",
    "Sleep has improved over the past week and appetite is returning to normal.",
    "Please follow up in two weeks to reassess mobility and any joint pain.",
]

# Imaging placeholders exercise the catalogue + skip path (no audio to transcribe).
IMAGING = [
    ("xray", "mock-chest-xray.txt"),
    ("mri", "mock-brain-mri.txt"),
    ("ultrasound_2d", "mock-abdominal-us.txt"),
]


def _render_speech(text: str, path: str) -> None:
    subprocess.run(
        ["espeak-ng", "-v", "en", "-s", "150", "-w", path, text],
        check=True,
        capture_output=True,
    )


def _upload(
    base_url: str, recipient: int, kind: str, filename: str, content_type: str, data: bytes
) -> None:
    import httpx

    resp = httpx.post(
        f"{base_url}/media",
        data={"care_recipient_id": str(recipient), "kind": kind},
        files={"file": (filename, data, content_type)},
        timeout=30.0,
    )
    resp.raise_for_status()
    body = resp.json()
    print(f"  uploaded {kind:14s} {filename:24s} -> {body['id']} ({body['status']})")


def main(argv: list[str] | None = None) -> None:
    s = Settings()
    parser = argparse.ArgumentParser(prog="media simulate")
    parser.add_argument("--recipient", type=int, default=1)
    parser.add_argument("--url", default=s.media_api_url)
    parser.add_argument(
        "--consults", type=int, default=len(SENTENCES),
        help="number of teleconsult recordings to synthesize (cycles the sentence list)",
    )
    args = parser.parse_args(argv)

    print(f"seeding synthetic media for recipient {args.recipient} -> {args.url}")
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(args.consults):
            text = SENTENCES[i % len(SENTENCES)]
            wav = Path(tmp) / f"consult-{i}.wav"
            _render_speech(text, str(wav))
            _upload(
                args.url, args.recipient, "teleconsult",
                f"consult-{i}.wav", "audio/wav", wav.read_bytes(),
            )
    for kind, filename in IMAGING:
        placeholder = f"SYNTHETIC MOCK {kind.upper()} — MaagapAruga demo, no real imaging.\n"
        _upload(
            args.url, args.recipient, kind, filename, "text/plain", placeholder.encode()
        )
    print("done. the worker will transcribe the consultations and index them for search.")


if __name__ == "__main__":
    main()
