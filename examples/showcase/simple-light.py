"""Showcase: simple + light. The neutral baseline — a clean sans-serif on white."""

from auditorium import Deck

deck = Deck(title="Simple · Light", theme=["simple", "light"])


@deck.slide
async def title(ctx):
    await ctx.title("Simple · Light")
    await ctx.subtitle("The neutral baseline")


@deck.slide
async def what(ctx):
    await ctx.md("## A clean default")
    await ctx.step()
    await ctx.md("- Sans-serif text on white")
    await ctx.md("- No chrome, no decoration")
    await ctx.md("- A safe starting point for any topic")


@deck.slide
async def code(ctx):
    await ctx.md("## Code")
    await ctx.md("""```python
def greet(name):
    print(f"hello, {name}")
```""")


@deck.slide
async def blocks(ctx):
    await ctx.md("## Callouts work too")
    await ctx.block("info", "Stackable themes mean *callouts inherit colours* from the active palette.")
    await ctx.step()
    await ctx.block("success", "Switch to a different colour theme and the same callout adapts.")


@deck.slide
async def fin(ctx):
    await ctx.title("Fin.")
    await ctx.subtitle("simple + light")
