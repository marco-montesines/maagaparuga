"""Worker transcription pipeline: one job -> searchable segments.

    fetch binary (claim-check) -> normalize audio (FFmpeg, 16 kHz mono)
    -> faster-whisper segments -> MiniLM embeddings -> OpenSearch index
    -> mark the asset indexed.

The FFmpeg step is a module-level function injected into the pipeline, so the
orchestration is unit-tested with fakes and no ffmpeg/whisper binary.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from .domain.models import AssetStatus, ProcessingJob, TranscriptSegment
from .ports import Catalog, Embedder, ObjectStore, Transcriber, TranscriptIndex


def normalize_audio(src_path: str, dst_path: str) -> None:
    """Decode any container/track to 16 kHz mono WAV (what Whisper expects)."""
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-y", "-i", src_path,
            "-ac", "1", "-ar", "16000", "-vn", "-f", "wav", dst_path,
        ],
        check=True,
        capture_output=True,
    )


class TranscriptionPipeline:
    def __init__(
        self,
        *,
        store: ObjectStore,
        catalog: Catalog,
        transcriber: Transcriber,
        embedder: Embedder,
        index: TranscriptIndex,
        normalize: Callable[[str, str], None] = normalize_audio,
    ) -> None:
        self._store = store
        self._catalog = catalog
        self._transcriber = transcriber
        self._embedder = embedder
        self._index = index
        self._normalize = normalize

    def process(self, job: ProcessingJob) -> int:
        """Run the job end to end; return the number of segments indexed."""
        self._catalog.set_status(job.asset_id, AssetStatus.PROCESSING)

        data = self._store.get(job.object_key)
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.bin"
            src.write_bytes(data)
            wav = Path(tmp) / "audio.wav"
            self._normalize(str(src), str(wav))
            spans = self._transcriber.transcribe(str(wav))

        segments = [
            TranscriptSegment(
                asset_id=job.asset_id,
                care_recipient_id=job.care_recipient_id,
                index=i,
                start_ms=start,
                end_ms=end,
                text=text,
            )
            for i, (start, end, text) in enumerate(spans)
        ]
        if segments:
            vectors = self._embedder.embed([s.text for s in segments])
            self._index.index_segments(segments, vectors)

        self._catalog.set_status(job.asset_id, AssetStatus.INDEXED)
        return len(segments)
