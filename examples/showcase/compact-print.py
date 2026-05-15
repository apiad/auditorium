"""Showcase: compact + print. Dense, monochrome, print-ready handouts."""

from auditorium import Deck

deck = Deck(title="Compact · Print", theme=["compact", "print"])


@deck.slide
async def title(ctx):
    await ctx.title("Quarterly Review")
    await ctx.subtitle("Compact handout, ready to print")


@deck.slide
async def summary(ctx):
    await ctx.md("## Summary")
    await ctx.md("""
| Quarter | Revenue | Growth |
|---------|--------:|-------:|
| Q1      | $1.2M   | +6%    |
| Q2      | $1.4M   | +17%   |
| Q3      | $1.5M   | +7%    |
| Q4      | $1.8M   | +20%   |
""")


@deck.slide
async def actions(ctx):
    await ctx.md("## Actions")
    await ctx.md("""
1. Approve FY-2026 budget envelope
2. Renew vendor contracts before EOM
3. Schedule strategy offsite in November
""")


@deck.slide
async def fin(ctx):
    await ctx.title("Distribute.")
    await ctx.subtitle("compact + print")
