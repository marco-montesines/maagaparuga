"""faster-whisper transcriber (CTranslate2 Whisper, int8 CPU).

Loaded once per worker process; weights are cached under ``WHISPER_CACHE_DIR``
(a PVC on-cluster) so a pod restart never re-downloads them. faster-whisper is
imported lazily so importing this module (and the fast test suite) stays cheap.
"""

from __future__ import annotations

from typing import Any

from ..config import Settings


class FasterWhisperTranscriber:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or Settings()
        self._model: Any | None = None

    def _load(self) -> Any:
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self._s.whisper_model,
                device="cpu",
                compute_type=self._s.whisper_compute_type,
                download_root=self._s.whisper_cache_dir or None,
            )
        return self._model

    def transcribe(self, audio_path: str) -> list[tuple[int, int, str]]:
        """Return (start_ms, end_ms, text) tuples in order, blanks dropped."""
        model = self._load()
        segments, _info = model.transcribe(audio_path, language="en", vad_filter=True)
        out: list[tuple[int, int, str]] = []
        for seg in segments:
            text = seg.text.strip()
            if text:
                out.append((int(seg.start * 1000), int(seg.end * 1000), text))
        return out
