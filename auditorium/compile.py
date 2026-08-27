"""Run a deck to produce a Timeline. Nothing is displayed and nothing sleeps."""
from __future__ import annotations

import inspect

import markdown

from auditorium.deck import Deck
from auditorium.scene import SceneContext
from auditorium.timeline import Marker, Timeline

SHIM_BEAT_HOLD_MS = 1500


def _notes_html(func) -> str:
    """Render a scene function's docstring as speaker notes.

    ``inspect.getdoc`` rather than ``__doc__`` because on Python 3.12 a
    docstring's continuation lines carry the source indentation, and markdown
    reads four leading spaces as a code block. CPython 3.13 strips it at
    compile time, but the project floor is 3.12.
    """
    doc = inspect.getdoc(func)
    return markdown.markdown(doc, extensions=["extra"]) if doc else ""


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

        ctx._tl.markers.append(
            Marker(t=ctx.t_ms, title=info.name, notes_html=_notes_html(info.func))
        )

        if is_scene:
            await info.func(ctx)
        else:
            from auditorium.slide import SlideContext
            await info.func(SlideContext(ctx))

    tl.audio = list(getattr(deck, "_audio", []))
    return tl
