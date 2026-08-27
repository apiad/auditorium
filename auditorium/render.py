"""Frame-stepped rendering. The fourth consumer of seek(t).

Nothing here reads a wall clock. Which timeline position each output frame
shows is decided by render_schedule() -- a pure function -- so the frame plan
can be tested without a browser, and so two renders of the same timeline
produce the same frames by construction rather than by luck.
"""
from __future__ import annotations

from auditorium.timeline import Timeline


def render_schedule(timeline: Timeline, fps: int) -> list[int]:
    """Return one timeline time (ms) per output frame, in order.

    Beats have no intrinsic length in the timeline, but a rendered video has
    to dwell on them or a slide deck blasts past every reveal. Each beat's
    hold_ms becomes repeated frames at that same timeline position, inserted
    where the beat sits.
    """
    duration = timeline.duration_ms
    if duration <= 0 and not timeline.beats:
        return []

    step_ms = 1000 / fps
    holds = {b.t: b.hold_ms for b in timeline.beats if b.hold_ms > 0}

    schedule: list[int] = []
    emitted_holds: set[int] = set()
    n = int(duration * fps / 1000)
    for i in range(n):
        t = int(i * step_ms)
        schedule.append(t)
        # Dwell on any beat this frame has just reached or passed.
        for beat_t, hold_ms in sorted(holds.items()):
            if beat_t in emitted_holds:
                continue
            if t >= beat_t:
                extra = int(hold_ms * fps / 1000)
                schedule.extend([t] * extra)
                emitted_holds.add(beat_t)
    return schedule


def frame_count(timeline: Timeline, fps: int) -> int:
    """Number of frames a render of this timeline will produce."""
    return len(render_schedule(timeline, fps))
