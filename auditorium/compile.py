"""Run a deck to produce a Timeline. Nothing is displayed and nothing sleeps."""
from __future__ import annotations

from auditorium.deck import Deck
from auditorium.scene import SceneContext
from auditorium.timeline import Timeline

SHIM_BEAT_HOLD_MS = 1500


async def compile_deck(deck: Deck) -> Timeline:
    """Execute every scene against a shared clock and return the timeline."""
    tl = Timeline(meta={"title": deck.title})
    ctx: SceneContext | None = None

    for index, info in enumerate(deck.slides):
        is_scene = getattr(info.func, "_auditorium_scene", False)
        hold = 0 if is_scene else SHIM_BEAT_HOLD_MS

        if ctx is None:
            ctx = SceneContext(tl, beat_hold_ms=hold)
        else:
            # Scene boundary: a beat, then wipe the stage, then continue on
            # the same clock. The clear lands after beat()'s 1ms bump, so the
            # outgoing scene is still whole *at* the beat where the presenter
            # is paused, and only clears once they advance.
            ctx._beat_hold_ms = hold
            await ctx.beat()
            await ctx.clear()

        if is_scene:
            await info.func(ctx)
        else:
            from auditorium.slide import SlideContext
            await info.func(SlideContext(ctx))

    return tl
