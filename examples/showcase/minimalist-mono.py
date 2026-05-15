"""Showcase: minimalist + mono. Ultra-restrained — emphasis by weight only."""

from auditorium import Deck

deck = Deck(title="Minimalist · Mono", theme=["minimalist", "mono"])


@deck.slide
async def title(ctx):
    await ctx.title("Less.")
    await ctx.subtitle("minimalist + mono")


@deck.slide
async def manifesto(ctx):
    await ctx.md("## Manifesto")
    await ctx.step()
    await ctx.md("- No accent colours")
    await ctx.step()
    await ctx.md("- No decoration")
    await ctx.step()
    await ctx.md("- Just **type**, weight, and the page")


@deck.slide
async def divider(ctx):
    await ctx.section("Pause")


@deck.slide
async def quote(ctx):
    await ctx.md("> Perfection is achieved, not when there is nothing more to add,\n"
                 "> but when there is nothing left to take away.")
    await ctx.md("*— Antoine de Saint-Exupéry*")


@deck.slide
async def fin(ctx):
    await ctx.title("End.")
