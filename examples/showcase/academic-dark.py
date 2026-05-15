"""Showcase: academic + dark. Serif typography on a deep slate background."""

from auditorium import Deck

deck = Deck(title="Academic · Dark", theme=["academic", "dark"])


@deck.slide
async def title(ctx):
    await ctx.title("On Continuity")
    await ctx.subtitle("A seminar talk, in the academic layout")


@deck.slide
async def divider(ctx):
    await ctx.section("Definitions", number="§ 1")


@deck.slide
async def continuity(ctx):
    await ctx.md("## Continuity")
    await ctx.block(
        "definition",
        "A function $f: X \\to Y$ is **continuous** at $x_0$ if for every "
        "$\\varepsilon > 0$ there exists $\\delta > 0$ such that "
        "$|x - x_0| < \\delta$ implies $|f(x) - f(x_0)| < \\varepsilon$.",
        title="Definition 1.1 (Continuity)",
    )


@deck.slide
async def evt(ctx):
    await ctx.md("## The Extreme Value Theorem")
    await ctx.block(
        "theorem",
        "Every continuous function on a compact set attains its maximum.",
        title="Theorem 1.2 (EVT)",
    )
    await ctx.step()
    await ctx.block(
        "proof",
        "By compactness, $f(K)$ is compact in $\\mathbb{R}$, hence closed "
        "and bounded — so $\\sup f(K) \\in f(K)$. $\\blacksquare$",
    )


@deck.slide
async def fin(ctx):
    await ctx.title("Q&A")
    await ctx.subtitle("academic + dark")
