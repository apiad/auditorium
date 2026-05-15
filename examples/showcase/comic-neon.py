"""Showcase: comic + neon. Playful display fonts over saturated cyan/magenta."""

from auditorium import Deck

deck = Deck(title="Comic · Neon", theme=["comic", "neon"])


@deck.slide
async def title(ctx):
    await ctx.title("BOOM!")
    await ctx.subtitle("comic + neon = a launch deck")


@deck.slide
async def pitch(ctx):
    await ctx.md("## What if presentations…")
    await ctx.step()
    await ctx.md("- were **fun**?")
    await ctx.step()
    await ctx.md("- were **fast**?")
    await ctx.step()
    await ctx.md("- ran from a **script**?")


@deck.slide
async def features(ctx):
    await ctx.title("The lineup")
    await ctx.block("success", "Live-reloading decks.")
    await ctx.step()
    await ctx.block("info", "Stackable themes — mix any layout with any palette.")
    await ctx.step()
    await ctx.block("warning", "Side effects may include enjoying public speaking.")


@deck.slide
async def fin(ctx):
    await ctx.title("Get it.")
    await ctx.subtitle("comic + neon")
    await ctx.md("`pip install auditorium`")
