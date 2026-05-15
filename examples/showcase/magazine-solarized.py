"""Showcase: magazine + solarized. Editorial layout with the classic palette."""

from auditorium import Deck

deck = Deck(title="Magazine · Solarized", theme=["magazine", "solarized"])


@deck.slide
async def title(ctx):
    await ctx.title("The Long Form")
    await ctx.subtitle("magazine + solarized — an editorial feel")


@deck.slide
async def lead(ctx):
    await ctx.md("## The Lede")
    await ctx.md("In the slow lane of the modern web, long-form writing has quietly "
                 "made a comeback. Newsletters, longreads, even *slides* are reclaiming "
                 "the reader's patience.")


@deck.slide
async def split(ctx):
    """Two-column editorial spread."""
    await ctx.md("## A Two-Column Spread")
    left, right = await ctx.columns(2)
    async with left:
        await ctx.md("""
        ### The argument

        - Density beats density.
        - White space sells the story.
        - Pull-quotes earn the reader's eye.
        """)
    async with right:
        await ctx.md("> Slow reading is a deliberate act of attention "
                     "in an age that punishes it.")


@deck.slide
async def fin(ctx):
    await ctx.title("Continued →")
    await ctx.subtitle("magazine + solarized")
