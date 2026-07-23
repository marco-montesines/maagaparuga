"""Assemble a NEWS2 ``VitalsSnapshot`` from a window of device samples.

Real IoMT devices are single-purpose (a pulse oximeter has no thermometer), so a
window contains many partial samples. NEWS2 needs one consolidated set, so for
each parameter the **latest non-null** value across the window is taken — the
most recent reading of each vital, regardless of which device produced it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

from .domain.models import Consciousness, VitalsSnapshot
from .ports import VitalsSampleDTO

T = TypeVar("T")


def assemble_snapshot(
    samples: Sequence[VitalsSampleDTO], *, on_oxygen: bool = False
) -> VitalsSnapshot:
    ordered = sorted(samples, key=lambda s: s.measured_at, reverse=True)

    def latest(getter: Callable[[VitalsSampleDTO], T | None]) -> T | None:
        for sample in ordered:
            value = getter(sample)
            if value is not None:
                return value
        return None

    def latest_consciousness() -> Consciousness | None:
        # UNSPECIFIED means "not reported" — treat it as absent so it does not
        # mask an earlier, actually-measured level.
        for sample in ordered:
            level = sample.consciousness
            if level is not None and level is not Consciousness.UNSPECIFIED:
                return level
        return None

    return VitalsSnapshot(
        respiratory_rate=latest(lambda s: s.respiratory_rate),
        spo2_percent=latest(lambda s: s.spo2_percent),
        body_temp_c=latest(lambda s: s.body_temp_c),
        bp_systolic=latest(lambda s: s.bp_systolic),
        heart_rate_bpm=latest(lambda s: s.heart_rate_bpm),
        consciousness=latest_consciousness(),
        on_oxygen=on_oxygen,
    )
