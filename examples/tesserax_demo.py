"""Auditorium + Tesserax: live vector graphics in slides.

Demonstrates that `ctx.show(canvas)` renders a tesserax ``Canvas`` automatically
via the Jupyter display protocol (``_repr_svg_``). Auditorium does NOT depend
on tesserax — this example relies on the ``examples`` optional-dependency group.

Run with:
    uv sync --extra examples
    uv run auditorium run examples/tesserax_demo.py
"""

from auditorium import Deck
from tesserax import Canvas, Circle, Square, Text
from tesserax.color import Colors
from tesserax.layout import RowLayout

deck = Deck(title="Auditorium + Tesserax")


@deck.slide
async def title(ctx):
    """Title slide."""
    await ctx.md("# Auditorium + Tesserax")
    await ctx.md("*Live vector graphics via the Jupyter display protocol*")


@deck.slide
async def direct(ctx):
    """The punchline: ctx.show(canvas) just works."""
    await ctx.md("## `await ctx.show(canvas)`")

    with Canvas() as canvas:
        with RowLayout():
            Square(40, fill=Colors.Green, stroke=Colors.Transparent)
            Text("auditorium", size=48, font="sans-serif", fill=Colors.Navy, anchor="middle")
            Circle(25, fill=Colors.Red, stroke=Colors.Transparent)

    await ctx.show(canvas.fit(padding=20))
    await ctx.step()
    await ctx.md("Auditorium has **zero** knowledge of tesserax — the SVG comes from `_repr_svg_`.")


@deck.slide
async def build_up(ctx):
    """Incrementally add shapes across steps — each ctx.show(canvas) re-renders the current state."""
    await ctx.md("## Canvas grows with the slide")

    canvas = Canvas()
    with canvas:
        Circle(40, fill=Colors.SkyBlue, stroke=Colors.Transparent).translated(-100, 0)

    await ctx.show(canvas.fit(padding=20))
    await ctx.step()

    with canvas:
        Circle(40, fill=Colors.Tomato, stroke=Colors.Transparent).translated(0, 0)

    await ctx.show(canvas.fit(padding=20))
    await ctx.step()

    with canvas:
        Circle(40, fill=Colors.Gold, stroke=Colors.Transparent).translated(100, 0)

    await ctx.show(canvas.fit(padding=20))
    await ctx.step()
    await ctx.md("Each `ctx.show(...)` appends a fresh `<div>` with the SVG — no DOM-level diffing needed.")


@deck.slide
async def fin(ctx):
    """Close."""
    await ctx.md("# One line, zero coupling")
    await ctx.md("`await ctx.show(canvas)` — that's the whole integration.")
    await ctx.md("*Same pattern works for matplotlib, pandas, altair, and any Jupyter-aware object.*")
