# Auditorium

[<img alt="PyPI - License" src="https://img.shields.io/pypi/l/auditorium.svg">](https://github.com/apiad/auditorium/blob/master/LICENSE)
[<img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/auditorium.svg">](https://pypi.org/project/auditorium/)
[<img alt="PyPI" src="https://img.shields.io/pypi/v/auditorium.svg">](https://pypi.org/project/auditorium/)

Auditorium is a Python framework for live technical presentations. You write slides as `async def` functions in a plain `.py` file, and Auditorium runs them as a live presentation in your browser — complete with keypress-gated reveals, timed animations, LaTeX math, syntax-highlighted code, and flexible layouts.

```python
from auditorium import Deck

deck = Deck(title="My Talk")

@deck.slide
async def hello(ctx):
    """Speaker notes go here — only visible in presenter view."""
    await ctx.md("# Hello, World!")
    await ctx.step()
    await ctx.md("This appeared after pressing right arrow.")
```

```bash
auditorium run talk.py
```

## How it works

Each slide is an `async def` decorated with `@deck.slide`. The docstring renders as Markdown when the slide loads. The function body is imperative Python that drives the presentation through awaitable primitives:

- **Content:** `show(html)`, `hide(selector)`, `replace(selector, html)`, `set_class(selector, cls)`, `remove_class(selector, cls)`
- **Markdown:** `md(text)`, `show_md(path)`
- **Timing:** `step()` (wait for keypress), `sleep(seconds)`
- **Layout:** `columns(sizing)`, `rows(sizing)`, `place(html, x, y)`

A FastAPI server runs your slide functions and pushes DOM mutations over WebSocket to a minimal browser client. Each browser tab gets its own independent session — you can have multiple tabs on different slides simultaneously.

## Installation

Requires Python 3.12+.

```bash
pip install auditorium
```

Or with uv:

```bash
uv add auditorium
```

## Usage

Create a file (e.g. `talk.py`) with a `Deck` instance and `@deck.slide` functions, then run:

```bash
auditorium run talk.py
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Host to bind to |
| `--port` | `8000` | Port to bind to |
| `--no-open` | (opens browser) | Don't auto-open the browser |
| `--no-watch` | (watches files) | Disable hot reload |

Hot reload is on by default — edit your `.py` file and the browser stays on the current slide while picking up changes. A small status dot in the bottom-left corner shows connection state (green = connected, red = disconnected, blinking orange = reconnecting).

## Navigation

| Key | Action |
|-----|--------|
| Right arrow / Space | Advance step, or next slide if no pending step |
| Page Down | Skip to next slide (cancel remaining steps) |
| Left arrow | Previous slide (re-runs from start) |
| `r` | Restart current slide |
| Digits + Enter | Jump to slide N |

## Presenter Mode

Press `p` during a presentation to open the presenter view in a new tab, or start with:

```bash
auditorium run talk.py --presenter
```

The presenter view shows:
- Current slide (mirrored from audience view)
- Speaker notes (from the slide's docstring)
- Next slide preview (name and first line of notes)
- Elapsed timer

## Layouts

Layout primitives return `Region` objects that scope insertion targets via `async with`:

```python
@deck.slide
async def side_by_side(ctx):
    """## Two Columns"""
    left, right = await ctx.columns([2, 1])

    async with left:
        await ctx.md("Main content (2/3 width)")

    async with right:
        await ctx.md("Sidebar (1/3 width)")
```

Sizing accepts integers (proportional), or `"auto"` for natural content size:

```python
@deck.slide
async def structured(ctx):
    """## Header / Body / Footer"""
    header, body, footer = await ctx.rows(["auto", 1, "auto"])

    async with header:
        await ctx.md("### Fixed Header")
    async with footer:
        await ctx.md("*Fixed footer*")
    async with body:
        await ctx.md("Body stretches to fill remaining space.")
```

Available: `columns(sizing)`, `rows(sizing)`, `place(html, x, y)`. They nest freely.

## Features

- **Speaker notes** — docstrings become private presenter notes
- **Presenter mode** — second tab with notes, timer, and slide preview
- **Static export** — PDF, HTML, or PNG via `auditorium export`
- **Progressive reveals** — `await ctx.step()` pauses for a keypress
- **Timed animations** — `await ctx.sleep(seconds)` for automatic pacing
- **LaTeX math** — KaTeX bundled, use `$...$` or `$$...$$` in Markdown
- **Code highlighting** — fenced code blocks highlighted by highlight.js (bundled)
- **Flexible layouts** — `columns`, `rows`, `place` with `"auto"` sizing
- **Hot reload** — edit and see changes instantly, staying on the same slide
- **Independent sessions** — each browser tab runs its own slide independently
- **Reconnection** — survives server restarts without losing your place
- **Video recording** — `auditorium record` captures presentations via Playwright
- **Fully offline** — all assets bundled, zero outbound requests, no build step

## Recording

Record your presentation to video (requires `pip install auditorium[record]` and `playwright install chromium`):

```bash
# Auto mode: headless, deterministic pacing
auditorium record talk.py -o talk.webm --auto-step 2.0

# Live mode: you drive, Playwright captures
auditorium record talk.py -o talk.webm --live
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output` / `-o` | `recording.webm` | Output file path |
| `--resolution` | `1920x1080` | Viewport size |
| `--auto-step` | `2.0` | Seconds per `step()` in auto mode |
| `--slide-delay` | `3.0` | Seconds to linger on completed slide before advancing |
| `--live` | off | Visible browser, manual navigation |

## Export

Export your presentation to static formats (requires `auditorium[record]`):

```bash
auditorium export talk.py -f html -o talk.html   # self-contained HTML
auditorium export talk.py -f pdf -o talk.pdf     # vector PDF
auditorium export talk.py -f png -o slides/      # one PNG per slide
```

## Example

See [`examples/demo_deck.py`](examples/demo_deck.py) for a complete deck exercising every feature.

```bash
auditorium run examples/demo_deck.py
```

## License

MIT
