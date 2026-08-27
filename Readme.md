# 🎓 Auditorium

[<img alt="PyPI - License" src="https://img.shields.io/pypi/l/auditorium.svg">](https://github.com/apiad/auditorium/blob/master/LICENSE)
[<img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/auditorium.svg">](https://pypi.org/project/auditorium/)
[<img alt="PyPI" src="https://img.shields.io/pypi/v/auditorium.svg">](https://pypi.org/project/auditorium/)

**The presentation framework for people who think in code.**

Auditorium lets you build live technical presentations as Python scripts. Each slide is an `async def` function. Animate algorithms step by step, render live-computed plots, run numerical demos — anything Python can do, your slides can do. No PowerPoint. No Markdown. Just code.

```python
from auditorium import Deck

deck = Deck(title="My Talk")

@deck.slide
async def sorting_demo(ctx):
    """Explain how the algorithm builds the sorted prefix."""
    await ctx.md("## Bubble Sort, Step by Step")
    data = [5, 3, 8, 1, 2]
    for i in range(len(data)):
        for j in range(len(data) - 1 - i):
            if data[j] > data[j + 1]:
                data[j], data[j + 1] = data[j + 1], data[j]
            await ctx.md(f"`{data}`")
            await ctx.sleep(0.5)
    await ctx.step()
    await ctx.md("**Sorted!**")
```

```bash
pip install auditorium
auditorium run talk.py
```

---

## ✨ Why Auditorium?

Most presentation tools treat slides as static documents. Auditorium treats them as **programs**.

- 🐍 **Run algorithms live** — sort arrays, traverse graphs, train models, all animated on stage
- 📊 **Compute content** — generate plots, tables, or LaTeX from data, not screenshots
- 📦 **Use any Python library** — numpy, matplotlib, pandas, whatever you import works
- 🌍 **Share with students worldwide** — `--public` gives every connected browser your live deck
- 🔗 **Go public** — `--public` gives you an instant shareable URL, no deployment needed
- 📤 **Render and share** — render to mp4 frame by frame, or ship a self-contained HTML bundle that replays the whole timeline

If you've ever wished you could `await` inside a PowerPoint slide, this is for you.

---

## 🚀 Quick Start

```bash
pip install auditorium    # or: uv add auditorium
```

Create `talk.py`:

```python
from auditorium import Deck

deck = Deck(title="My Talk")

@deck.slide
async def intro(ctx):
    """Notes for the presenter — only visible in presenter view."""
    await ctx.md("# Welcome!")
    await ctx.md("*Press right arrow to continue*")

@deck.slide
async def demo(ctx):
    """Show progressive reveals and timed content."""
    await ctx.md("## Key Points")
    await ctx.step()
    await ctx.md("- First point")
    await ctx.step()
    await ctx.md("- Second point")
    await ctx.sleep(1)
    await ctx.md("*(that one appeared automatically)*")
```

Run it:

```bash
auditorium run talk.py
```

---

## 📋 Features

| | Feature | Description |
|---|---------|-------------|
| 🐍 | **Imperative Python slides** | Each slide is an `async def` — loops, conditionals, imports, anything |
| 🧪 | **Jupyter display protocol** | `ctx.show(obj)` renders any `_repr_html_` / `_repr_svg_` / `_repr_png_` object — matplotlib, pandas, altair, tesserax, … |
| 👁️ | **Progressive reveals** | `await ctx.step()` pauses for keypress, `await ctx.sleep(n)` auto-advances |
| 🧮 | **LaTeX math** | KaTeX bundled — `$inline$` and `$$display$$` in any markdown |
| 💻 | **Syntax highlighting** | Fenced code blocks with highlight.js (bundled) |
| 📐 | **Flexible layouts** | `columns`, `rows` with `"auto"` sizing, arbitrarily nested |
| 🎤 | **Presenter mode** | `--presenter` — notes, timer, stage mirror, next-scene preview |
| 🔄 | **Shared navigation** | Presenter drives all audience tabs; audience keyboards are inert |
| 🌍 | **Public sharing** | `--public` bridges to a relay — instant shareable URL, no deployment |
| 🕐 | **Late-join sync** | New viewers see the full slide state immediately |
| 📄 | **HTML / PNG export** | Self-contained interactive HTML, or PNG stills. No PDF — see below |
| 🎬 | **Deterministic video** | `auditorium render` steps frames against a paused timeline — two renders are byte-identical |
| 🔀 | **Frame ranges** | `--from`/`--to` make parallel rendering a shell-level fan-out |
| 🎛️ | **Preview client** | `auditorium preview` — scrubber, frame stepping, loop-a-range |
| ♻️ | **Hot reload** | Edit your `.py` and the browser updates instantly, holding your position |
| 📡 | **Offline** | All assets bundled — zero CDN, zero internet required |
| 🔌 | **Auto-reconnect** | Survives server restarts without losing your place |

---

## 🌍 Share Publicly

Present from your laptop, share with the world:

```bash
auditorium run talk.py --public
```

```
╭───────────────────────── Auditorium ─────────────────────────╮
│ Deck:   My Talk                                               │
│ Slides: 15                                                    │
│ URL:    http://127.0.0.1:8000                                 │
│ Mode:   independent (per-tab)                                 │
╰──────────────────────────────────────────────────────────────╯

Public URL: http://vps.apiad.net:4243/r/my-talk/
```

Anyone with the link sees your presentation in real time. No deployment, no hosting — your laptop runs the deck, a lightweight relay forwards it.

```bash
# Choose your own URL slug
auditorium run talk.py --public --name my-talk

# Use your own relay server
auditorium run talk.py --public --relay myserver.com:4243
```

**Self-host a relay** (it's one command):

```bash
auditorium relay                    # run directly
make relay-install                  # install as systemd service
make relay-update                   # pull + sync + restart
```

---

## 🎛️ Preview

`auditorium preview talk.py` opens the authoring surface: the stage plus a
transport bar.

```bash
auditorium preview talk.py
```

- 🎚️ **Scrubber** with a tick per beat, so you can see the structure of the timeline
- 🎞️ **Frame stepping** with `.` and `,` — one output frame at a time
- 🔁 **Loop a range** with `i`, `o` and `l`, to tune one animation without replaying the deck
- ♻️ **Hot reload holds your position** — edit the `.py` and you stay at the same instant

The frame counter reports **rendered** frames, including the dwell a render
spends on each beat — so the number beside the scrubber is the number you can
pass to `--from` / `--to`. The stage is the render target scaled down, not a
reflowed copy of it, so what you are looking at is what the mp4 will contain.

---

## 🎤 Presenter Mode

Start with `--presenter` to sync all audience tabs to your navigation:

```bash
auditorium run talk.py --presenter
```

Two tabs open: your **presenter view** (notes + timer + slide mirror + next-slide preview) and the **audience view**. Navigate from the presenter tab — every connected browser follows in real time.

- 📝 Docstrings become **speaker notes** (never shown to the audience)
- ⚡ Late-joining tabs catch up instantly (full slide state replayed)
- 🔒 Audience keyboards are locked — only the presenter navigates, enforced by the server rather than by the audience's good manners

The presenter broadcasts *intent* — "seek to t", "play from here to there" — not
positions. Every surface runs the same deterministic engine over the same
timeline, so a command is enough and there is nothing to drift.

Without `--presenter`, each tab navigates independently.

---

## 📐 Layouts

```python
@deck.slide
async def layout_demo(ctx):
    """Layouts nest freely."""
    await ctx.md("## Two Columns")
    left, right = await ctx.columns([2, 1])

    async with left:
        await ctx.md("Main content (2/3 width)")

    async with right:
        await ctx.md("Sidebar (1/3)")
```

Use `"auto"` for natural-size regions:

```python
header, body, footer = await ctx.rows(["auto", 1, "auto"])
```

---

## 🧪 Show Any Jupyter Object

`ctx.show(...)` speaks the **Jupyter display protocol**. Pass any object that implements `_repr_html_`, `_repr_svg_`, `_repr_png_`, or `_repr_jpeg_` and it just renders — no adapters, no bundling, no glue code.

```python
import pandas as pd
import matplotlib.pyplot as plt
from tesserax import Canvas, Circle, Square
from tesserax.layout import RowLayout

@deck.slide
async def live_data(ctx):
    # A pandas DataFrame — _repr_html_
    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    await ctx.show(df)

    # A matplotlib figure — _repr_png_ (or _repr_svg_ with the svg backend)
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [4, 5, 6])
    await ctx.show(fig)

    # A tesserax Canvas — _repr_svg_
    with Canvas() as canvas:
        with RowLayout():
            Square(30, fill="green")
            Circle(20, fill="red")
    await ctx.show(canvas.fit(padding=10))
```

This works with **matplotlib** figures, **pandas** DataFrames, **altair** charts, **plotly** figures, **tesserax** canvases, **sympy** expressions, **IPython** rich objects, and anything else in the Jupyter ecosystem. Plain strings are still passed through as HTML. Runnable example: [`examples/tesserax_demo.py`](examples/tesserax_demo.py).

---

## 🎬 Rendering & Export

Requires `pip install auditorium[record]` and `playwright install chromium`.

```bash
# Export a self-contained HTML bundle, or PNG stills
auditorium export talk.py -f html -o talk.html
auditorium export talk.py -f png -o slides/
```

```bash
# Render to video, frame by frame
auditorium render talk.py -o talk.mp4
auditorium render talk.py -o clip.mp4 --size vertical --fps 60
auditorium render talk.py -o frames/ --format png-sequence

# Render a frame range -- fan several out in parallel, then concat
auditorium render talk.py -o part1.mp4 --from 0 --to 300
```

`render` replaces the old `record`. `record` screen-captured a live browser,
so a loaded machine produced a different video; `render` steps frames against
a paused timeline, and two renders of the same deck are byte-identical.

### Why there is no PDF export

**Auditorium 4.0 removed PDF export, deliberately. It is not coming back.**

A deck is no longer a list of slides — it is a timeline. A scene is a
continuous function of time, so there is no canonical instant to print. Every
answer to "which moment becomes a page?" is invented rather than derived: the
end of each scene loses every build stage, one page per pause produces a run of
near-identical cumulative pages, and asking the author to name capture points
is a knob nobody wants to turn.

PNG and HTML export survive because both *are* total functions of the timeline.
A PNG is "the frame at time *t*", well-defined for any scene. The HTML bundle
carries the whole timeline and replays it. Neither has to guess.

**If you want a PDF**, that is a real thing to want — but you are the one who
knows which instants matter. Export PNGs, pick your frames, and assemble them:

```bash
auditorium export talk.py -f png -o slides/
img2pdf slides/*.png -o talk.pdf
```

**If the document was always meant to be printed**, do not start here. Author
it in a document engine — [scriptorium](https://github.com/apiad/scriptorium)
ships a `deck` theme for 16:9 slides and is built for pagination, which is a
genuinely hard problem and not this project's problem. Auditorium is for
animation. Print is a different craft, and pretending otherwise produced the
worst code in this repository.

---

## ⌨️ Navigation

Time is a coordinate in 4.0, so navigation moves between **beats** — the pause
points `await ctx.step()` and `await s.beat()` record — rather than between
slide indices.

**Present and presenter views:**

| Key | Action |
|-----|--------|
| → / Space / Page Down | Play to the next beat (skip to it if already playing) |
| ← / Page Up | Back to the previous beat |
| `r` | Restart from the beginning |
| End | Jump to the end |

**Preview client** (`auditorium preview`) adds:

| Key | Action |
|-----|--------|
| Space | Play / pause |
| `.` / `,` | Step one frame forward / back |
| `i` / `o` | Set the loop in / out point to the current time |
| `l` / `x` | Toggle looping / clear the loop |
| Home / End | Jump to the start / end |

Backward navigation resets the timeline and replays forward. That is deliberate:
seeking is path-dependent, so a rewound state and a freshly-seeked one would
otherwise differ — and the renderer only ever travels forward. Replaying is what
keeps what you see equal to what you get.

---

## 📚 Example

See [`examples/demo_deck.py`](examples/demo_deck.py) for a full 11-slide deck exercising every feature.

```bash
auditorium run examples/demo_deck.py
```

---

## 📜 License

MIT
