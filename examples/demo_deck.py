"""A demonstration deck exercising the full Auditorium vocabulary."""

from auditorium import Deck

deck = Deck(title="Auditorium Demo")


@deck.slide
async def title_slide(ctx):
    """Welcome the audience. Mention this is a demo of Auditorium 3.0."""
    await ctx.md("# Auditorium 3.0")
    await ctx.md("*Python-scripted live presentations*")


@deck.slide
async def progressive_reveal(ctx):
    """Show how step() works. Pause between each point for effect."""
    await ctx.md("## Progressive Reveals")
    await ctx.md("Each point appears on keypress:")
    await ctx.step()
    await ctx.md("- First, we **set up** the problem")
    await ctx.step()
    await ctx.md("- Then, we **explore** solutions")
    await ctx.step()
    await ctx.md("- Finally, we **conclude**")


@deck.slide
async def timed_content(ctx):
    """Timed content auto-advances. No keypress needed for this slide."""
    await ctx.md("## Timed Animations")
    await ctx.md("Watch the countdown:")
    for i in range(3, 0, -1):
        await ctx.md(f"### {i}...")
        await ctx.sleep(1)
    await ctx.md("### Go!")


@deck.slide
async def code_example(ctx):
    """Show a code example. The code block gets syntax highlighting via highlight.js."""
    await ctx.md("""## Code Highlighting

```python
from auditorium import Deck

deck = Deck(title="My Talk")

@deck.slide
async def hello(ctx):
    await ctx.md("# Hello, World!")
    await ctx.step()
    await ctx.md("This is **auditorium**.")
```
""")


@deck.slide
async def math_example(ctx):
    """KaTeX renders math. Both inline and display mode work."""
    await ctx.md("## Mathematics with KaTeX")
    await ctx.md("Euler's identity:")
    await ctx.step()
    await ctx.md("$$e^{i\\pi} + 1 = 0$$")
    await ctx.step()
    await ctx.md("The Gaussian integral:")
    await ctx.step()
    await ctx.md("$$\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}$$")


@deck.slide
async def two_columns(ctx):
    """Demonstrate columns layout with 2:1 ratio."""
    await ctx.md("## Two-Column Layout")
    left, right = await ctx.columns([2, 1])

    async with left:
        await ctx.md("""
        ### Left Column

        This is the main content area, taking up
        two-thirds of the width.

        - Point A
        - Point B
        - Point C
        """)

    async with right:
        await ctx.md("""
        ### Right Column

        This is the sidebar, taking up one-third.

        > A useful note.
        """)


@deck.slide
async def header_body_footer(ctx):
    """Show the auto sizing pattern. Header and footer stay fixed, body stretches."""
    await ctx.md("## Header / Body / Footer")
    header, body, footer = await ctx.rows(["auto", 1, "auto"])

    async with header:
        await ctx.md("### Fixed Header")

    async with footer:
        await ctx.md("*Fixed footer — always at the bottom.*")

    async with body:
        await ctx.md("This body region **stretches** to fill the available space.")
        await ctx.step()
        await ctx.md("Add more content and the body grows, but the header and footer stay put.")
        await ctx.step()
        await ctx.md("This is `rows([\"auto\", 1, \"auto\"])` — the classic flexbox pattern.")


@deck.slide
async def progressive_list(ctx):
    """Top-aligned progressive content. Uses rows(["auto", 1]) as a stable-top replacement."""
    await ctx.md("## Progressive List (Top-Aligned)")
    content, _spacer = await ctx.rows(["auto", 1])

    async with content:
        await ctx.md("New lines appear at the top, pushing down:")
        await ctx.step()
        await ctx.md("1. First item — reading position stays stable")
        await ctx.step()
        await ctx.md("2. Second item — no content reflow")
        await ctx.step()
        await ctx.md("3. Third item — content grows downward")
        await ctx.step()
        await ctx.md("4. Fourth item — this is what `stable_top` was for")


@deck.slide
async def mixed_timing(ctx):
    """Show how step() and sleep() can be combined in one slide."""
    await ctx.md("## Mixed Timing Models")
    await ctx.md("Combining keypress and timed reveals:")
    await ctx.step()

    await ctx.md("Loading...")
    await ctx.sleep(0.5)
    await ctx.md("**25%** complete")
    await ctx.sleep(0.5)
    await ctx.md("**50%** complete")
    await ctx.sleep(0.5)
    await ctx.md("**75%** complete")
    await ctx.sleep(0.5)
    await ctx.md("**100%** — Done!")

    await ctx.step()
    await ctx.md("*Press right arrow to continue*")


@deck.slide
async def nested_layout(ctx):
    """Nested layouts: rows inside columns inside rows. All combinations work."""
    await ctx.md("## Nested Layouts")
    top, bottom = await ctx.rows(2)

    async with top:
        left, right = await ctx.columns(2)
        async with left:
            await ctx.md("### Top-Left")
        async with right:
            await ctx.md("### Top-Right")

    async with bottom:
        await ctx.md("### Bottom (full width)")
        await ctx.md("Rows inside columns inside rows — it all nests cleanly.")


@deck.slide
async def fin(ctx):
    """Thank the audience. Mention the GitHub repo."""
    await ctx.md("# Thank You")
    await ctx.md("Built with **Auditorium 3.0**")
    await ctx.md("*github.com/apiad/auditorium*")
