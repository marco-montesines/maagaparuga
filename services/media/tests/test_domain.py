from __future__ import annotations

from media.adapters.queue_nats import decode_job, encode_job
from media.domain.models import MediaKind, ProcessingJob, TranscriptSegment


def test_only_teleconsult_has_audio() -> None:
    assert MediaKind.TELECONSULT.has_audio is True
    for imaging in (
        MediaKind.XRAY,
        MediaKind.ULTRASOUND_2D,
        MediaKind.ULTRASOUND_3D,
        MediaKind.ULTRASOUND_4D,
        MediaKind.MRI,
    ):
        assert imaging.has_audio is False


def test_segment_id_is_stable_and_scoped() -> None:
    seg = TranscriptSegment(
        asset_id="abc", care_recipient_id=1, index=3, start_ms=0, end_ms=500, text="hi"
    )
    assert seg.segment_id == "abc:3"


def test_job_codec_roundtrip() -> None:
    job = ProcessingJob(
        asset_id="a1", care_recipient_id=7, kind=MediaKind.TELECONSULT, object_key="7/a1/x.mp4"
    )
    assert decode_job(encode_job(job)) == job
