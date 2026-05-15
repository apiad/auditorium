"""A demonstration deck exercising the full Auditorium vocabulary.

Organised by section dividers so the tour is easy to follow:

    Intro → Layouts → Animations → Blocks → Typography → Themes

Use as living documentation: every primitive should appear at least once,
and every change to behaviour should be reflected here.
"""

from auditorium import Deck

deck = Deck(title="Auditorium 3.5 Tour", theme=["simple", "light"])


# --- Intro -------------------------------------------------------------

@deck.slide
async def title_slide(ctx):
    """Welcome the audience. The headline tour of Auditorium 3.5."""
    await ctx.title("Auditorium 3.5")
    await ctx.subtitle("Python-scripted live presentations")
    await ctx.step()
    await ctx.md("*A tour of every primitive — in one deck.*")


@deck.slide
async def section_intro(ctx):
    await ctx.section("Intro", number="01")


@deck.slide
async def what_is_auditorium(ctx):
    """One-screen elevator pitch."""
    await ctx.title("What is Auditorium?")
    await ctx.step()
    await ctx.md("- Slides are `async def` functions")
    await ctx.step()
    await ctx.md("- A FastAPI server pushes DOM mutations over WebSocket")
    await ctx.step()
    await ctx.md("- The browser is a dumb client — no build step")
    await ctx.step()
    await ctx.md("- Themes are stackable CSS files. No JS required.")


# --- Layouts -----------------------------------------------------------

@deck.slide
async def section_layouts(ctx):
    await ctx.section("Layouts", number="02")


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


# --- Animations --------------------------------------------------------

@deck.slide
async def section_animations(ctx):
    await ctx.section("Animations", number="03")


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


# --- Blocks ------------------------------------------------------------

@deck.slide
async def section_blocks(ctx):
    await ctx.section("Blocks", number="04")


@deck.slide
async def info_blocks(ctx):
    """Demonstrate the generic info blocks: note, info, success, warning, error, tip."""
    await ctx.title("Info Blocks")
    await ctx.subtitle("Coloured callouts for the common cases")
    await ctx.block("note", "A neutral aside that doesn't fit the main flow.")
    await ctx.step()
    await ctx.block("info", "Useful background context the reader may not know.")
    await ctx.step()
    await ctx.block("success", "The migration completed; **42 rows** updated.")
    await ctx.step()
    await ctx.block("warning", "This API will be deprecated in `v3.0`.")
    await ctx.step()
    await ctx.block("error", "Connection refused — check that the server is running.")


@deck.slide
async def academic_blocks(ctx):
    """Demonstrate the academic blocks: definition, theorem, proof, example, remark."""
    await ctx.title("Academic Blocks")
    await ctx.subtitle("For papers, lectures, and seminar talks")
    await ctx.block(
        "definition",
        "A function $f: X \\to Y$ is **continuous** at $x_0$ if for every "
        "$\\varepsilon > 0$ there exists $\\delta > 0$ such that "
        "$|x - x_0| < \\delta$ implies $|f(x) - f(x_0)| < \\varepsilon$.",
        title="Definition 2.1 (Continuity)",
    )
    await ctx.step()
    await ctx.block(
        "theorem",
        "Every continuous function on a compact set attains its maximum.",
        title="Theorem 2.3 (Extreme Value)",
    )
    await ctx.step()
    await ctx.block(
        "proof",
        "By compactness, the image $f(K)$ is compact in $\\mathbb{R}$, hence "
        "closed and bounded — so $\\sup f(K) \\in f(K)$. $\\blacksquare$",
    )
    await ctx.step()
    await ctx.block(
        "example",
        "$f(x) = x^2$ on $[-1, 1]$ attains its max value $1$ at $x = \\pm 1$.",
    )


# --- Typography --------------------------------------------------------

@deck.slide
async def section_typography(ctx):
    await ctx.section("Typography", number="05")


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
async def tables_demo(ctx):
    """Tables get booktabs-style rules in the academic theme."""
    await ctx.md("## Tables")
    await ctx.md("""
| Method  | Acc.  | F1    |
|---------|------:|------:|
| Linear  | 0.81  | 0.79  |
| Tree    | 0.86  | 0.85  |
| MLP     | 0.89  | 0.88  |
""")


@deck.slide
async def jupyter_display(ctx):
    """Show that ctx.show honors the Jupyter display protocol.

    Any object that implements `_repr_html_`, `_repr_svg_`, `_repr_png_`, or
    `_repr_jpeg_` renders automatically — matplotlib figures, pandas
    DataFrames, altair charts, tesserax canvases, and any custom class.
    """

    class Badge:
        """Tiny demo class with a _repr_html_ method."""

        def __init__(self, label: str, color: str) -> None:
            self.label, self.color = label, color

        def _repr_html_(self) -> str:
            return (
                f'<span style="display:inline-block;padding:0.3em 0.8em;'
                f"margin:0.2em;border-radius:999px;background:{self.color};"
                f'color:white;font-weight:600">{self.label}</span>'
            )

    await ctx.md("## Jupyter Display Protocol")
    await ctx.md("`ctx.show(obj)` honors `_repr_html_` / `_repr_svg_` / `_repr_png_` automatically.")
    await ctx.step()
    await ctx.show(Badge("matplotlib", "#1f77b4"))
    await ctx.show(Badge("pandas", "#ff7f0e"))
    await ctx.show(Badge("altair", "#2ca02c"))
    await ctx.show(Badge("tesserax", "#d62728"))
    await ctx.step()
    await ctx.md("Any Jupyter-aware object works — no adapters, no bundling.")


# --- Themes ------------------------------------------------------------

@deck.slide
async def section_themes(ctx):
    await ctx.section("Themes", number="06")


@deck.slide
async def themes_overview(ctx):
    """Themes are stackable CSS — orthogonal axes you compose."""
    await ctx.title("Stackable Themes")
    await ctx.subtitle("Two axes — layout & color — composed by CSS cascade")
    await ctx.step()
    await ctx.md("**Layout**: `simple`, `academic`, `comic`, `compact`, `minimalist`, `magazine`, `terminal`")
    await ctx.step()
    await ctx.md("**Color**: `light`, `dark`, `neon`, `print`, `solarized`, `pastel`, `mono`")
    await ctx.step()
    await ctx.md("Mix and match: `Deck(theme=[\"academic\", \"dark\"])`")


@deck.slide
async def transitions_demo(ctx):
    """Each theme can declare its own transition; --transition overrides."""
    await ctx.title("Slide Transitions")
    await ctx.subtitle("CSS-only animation, theme-declared")
    await ctx.step()
    await ctx.md("- `fade` — gentle opacity")
    await ctx.md("- `slide-left` — horizontal slide-in")
    await ctx.md("- `slide-up` — vertical lift")
    await ctx.md("- `zoom` — subtle scale-in")
    await ctx.md("- `none` — instant cuts (e.g. for print)")
    await ctx.step()
    await ctx.md("Override per deck with `Deck(transition=...)` or per run with `--transition`.")


# --- Outro -------------------------------------------------------------

@deck.slide
async def fin(ctx):
    """Thank the audience. Mention the GitHub repo."""
    await ctx.title("Thank You")
    await ctx.subtitle("Built with Auditorium 3.5")
    await ctx.md("*github.com/apiad/auditorium*")
