"""Showcase: terminal + pastel. Monospace structure, softened palette."""

from auditorium import Deck

deck = Deck(title="Terminal · Pastel", theme=["terminal", "pastel"])


@deck.slide
async def title(ctx):
    await ctx.title("$ ./talk")
    await ctx.subtitle("terminal + pastel")


@deck.slide
async def install(ctx):
    await ctx.md("## Install")
    await ctx.md("""```bash
$ uv add auditorium
$ uv run auditorium run deck.py
```""")


@deck.slide
async def code(ctx):
    await ctx.md("## Hello, World")
    await ctx.md("""```python
from auditorium import Deck

deck = Deck(title="Hi")

@deck.slide
async def hello(ctx):
    await ctx.md("# Hello!")
```""")


@deck.slide
async def shell(ctx):
    await ctx.md("## Shell")
    await ctx.md("""```bash
$ auditorium run deck.py --theme terminal --theme pastel
✓ Listening on http://127.0.0.1:8000
```""")
    await ctx.step()
    await ctx.block("tip", "Pass `--theme` more than once to stack layouts and palettes.")


@deck.slide
async def fin(ctx):
    await ctx.title("$ exit")
    await ctx.subtitle("terminal + pastel")
