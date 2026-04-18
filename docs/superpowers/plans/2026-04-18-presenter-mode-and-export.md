# Presenter Mode + Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add presenter mode (notes, timer, slide mirror) with docstrings-as-notes breaking change, and `auditorium export` command producing interactive HTML playback, vector PDF, or PNG screenshots via mutation recording.

**Architecture:** Docstrings stop rendering as content (breaking change → v3.0). Server sends `notes` and `next_preview` messages alongside mutations. New `/presenter` route serves a two-pane HTML view. Export runs the deck via Playwright, intercepts all websocket mutations into a timeline, and builds self-contained outputs from that timeline. HTML export replays the full presentation interactively (steps wait for keypress, sleeps auto-advance).

**Tech Stack:** Existing FastAPI/WebSocket server, Playwright (optional dep for export), markdown library for notes rendering.

---

### File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `auditorium/server.py:148-150` | Modify | Remove docstring-as-content rendering, send `notes` + `next_preview` messages |
| `auditorium/deck.py` | Read-only | `SlideInfo.name` and `func.__doc__` already accessible |
| `examples/demo_deck.py` | Rewrite | Move all docstring content to `md()` calls, add presenter notes as docstrings |
| `auditorium/static/presenter.html` | Create | Presenter view HTML with two-pane layout |
| `auditorium/static/index.html` | Modify | Add `p` keypress to open presenter, ignore `notes`/`next_preview` messages |
| `auditorium/static/theme.css` | Modify | Add presenter view styles |
| `auditorium/server.py:77-80` | Modify | Add `/presenter` route |
| `auditorium/cli.py:54-90` | Modify | Add `--presenter` flag to `run` command |
| `auditorium/exporter.py` | Create | Export logic: start server, Playwright captures final DOM/screenshot/PDF per slide |
| `auditorium/cli.py` | Modify | Add `export` command |
| `pyproject.toml` | Modify | Bump to `1!3.0.0` |
| `auditorium/cli.py:15-18` | Modify | Update version string |
| `Readme.md` | Modify | Update for v3.0 changes |
| `CHANGELOG.md` | Modify | Add v3.0 entry |
| `CLAUDE.md` | Modify | Update architecture docs |

---

### Task 1: Breaking change — docstrings become notes

**Files:**
- Modify: `auditorium/server.py:133-164` (`_run_slide`)

- [ ] **Step 1: Replace docstring rendering with notes + next_preview messages**

In `auditorium/server.py`, replace `_run_slide` (lines 133-164) with:

```python
async def _run_slide(app: FastAPI, session: Session) -> None:
    """Run a slide function for a specific session."""
    deck = app.state.deck
    index = session.current_slide
    if not deck or index >= len(deck.slides):
        return
    try:
        await session.send({"type": "clear"})
        await session.send({"type": "slide", "index": index, "total": len(deck.slides)})

        slide_fn = deck.slides[index]

        # Send presenter notes (docstring rendered as markdown)
        notes_html = ""
        if slide_fn.func.__doc__:
            import textwrap
            import markdown
            notes_html = markdown.markdown(
                textwrap.dedent(slide_fn.func.__doc__).strip(),
                extensions=["fenced_code", "tables"],
            )
        await session.send({"type": "notes", "html": notes_html})

        # Send next slide preview
        if index < len(deck.slides) - 1:
            next_fn = deck.slides[index + 1]
            next_excerpt = ""
            if next_fn.func.__doc__:
                import textwrap
                lines = textwrap.dedent(next_fn.func.__doc__).strip().split("\n")
                # First non-empty paragraph
                para = []
                for line in lines:
                    if line.strip() == "" and para:
                        break
                    if line.strip():
                        para.append(line.strip())
                next_excerpt = " ".join(para)
            await session.send({"type": "next_preview", "title": next_fn.name, "excerpt": next_excerpt})
        else:
            await session.send({"type": "next_preview", "title": None, "excerpt": ""})

        # Execute the slide body (docstring is NOT rendered as content)
        from auditorium.slide import SlideContext
        ctx = SlideContext(session)
        await slide_fn.func(ctx)

        # Auto-advance in recording mode
        if session.auto_step is not None:
            await asyncio.sleep(session.slide_delay)
            if index < len(deck.slides) - 1:
                session.current_slide = index + 1
                session.slide_task = asyncio.create_task(_run_slide(app, session))
                return
            await session.send({"type": "finished"})
    except (asyncio.CancelledError, Exception):
        pass
```

- [ ] **Step 2: Commit**

```bash
git add auditorium/server.py
git commit -m "feat!: docstrings are now presenter notes, not slide content

BREAKING: slide docstrings no longer render as visible content.
Use md() for all visible content. Docstrings are sent as notes
for the presenter view."
```

---

### Task 2: Migrate demo_deck.py to md()-only content

**Files:**
- Rewrite: `examples/demo_deck.py`

- [ ] **Step 1: Rewrite demo_deck.py**

Move all visible content from docstrings to `md()` calls. Add meaningful presenter notes as docstrings.

```python
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
```

- [ ] **Step 2: Test that the deck runs**

```bash
uv run auditorium run examples/demo_deck.py --no-open --port 8790 &
sleep 2
# Quick websocket test: connect and verify slide loads
uv run python << 'PYEOF'
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://127.0.0.1:8790/ws') as ws:
        await ws.send(json.dumps({'type': 'hello', 'slide': 0}))
        msgs = []
        while True:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                if msg.get('id'): await ws.send(json.dumps({'type': 'ack', 'id': msg['id']}))
                msgs.append(msg)
            except asyncio.TimeoutError: break
        notes = [m for m in msgs if m.get('type') == 'notes']
        muts = [m for m in msgs if m.get('type') == 'mutation']
        print(f'Notes messages: {len(notes)}, Mutations: {len(muts)}')
        if notes: print(f'Notes content present: {bool(notes[0].get("html"))}')
        print('OK' if muts else 'FAIL: no mutations')
asyncio.run(test())
PYEOF
kill $(lsof -t -i:8790) 2>/dev/null
```

- [ ] **Step 3: Commit**

```bash
git add examples/demo_deck.py
git commit -m "feat!: migrate demo_deck to md()-only content with presenter notes"
```

---

### Task 3: Create presenter view HTML

**Files:**
- Create: `auditorium/static/presenter.html`
- Modify: `auditorium/static/theme.css`

- [ ] **Step 1: Create presenter.html**

Create `auditorium/static/presenter.html`. This is a two-pane layout: left = slide mirror (receives same mutations), right = notes + next preview + timer. It shares the same JS mutation logic as `index.html` but adds handlers for `notes` and `next_preview` message types.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Auditorium — Presenter</title>
    <link rel="stylesheet" href="/static/theme.css">
    <link rel="stylesheet" href="/static/vendor/katex/katex.min.css">
    <link rel="stylesheet" href="/static/vendor/hljs/styles/github.min.css">
    <script src="/static/vendor/katex/katex.min.js"></script>
    <script src="/static/vendor/katex/contrib/auto-render.min.js"></script>
    <script src="/static/vendor/hljs/highlight.min.js"></script>
</head>
<body>
    <div id="presenter-container">
        <div id="slide-pane">
            <div id="slide-root"></div>
        </div>
        <div id="info-pane">
            <div id="notes"></div>
            <div id="next-preview">
                <div id="next-title"></div>
                <div id="next-excerpt"></div>
            </div>
            <div id="presenter-footer">
                <span id="timer">00:00</span>
                <span id="slide-indicator"></span>
            </div>
        </div>
    </div>
    <div id="connection-status"></div>

    <script>
    (function() {
        const root = document.getElementById('slide-root');
        const indicator = document.getElementById('slide-indicator');
        const statusEl = document.getElementById('connection-status');
        const notesEl = document.getElementById('notes');
        const nextTitle = document.getElementById('next-title');
        const nextExcerpt = document.getElementById('next-excerpt');
        const timerEl = document.getElementById('timer');
        let ws = null;
        let targetStack = [root];
        let timerStart = null;
        let timerInterval = null;

        function currentTarget() {
            return targetStack[targetStack.length - 1];
        }

        function getSlideFromHash() {
            const match = location.hash.match(/#slide-(\d+)/);
            return match ? parseInt(match[1], 10) : 0;
        }

        function setStatus(state) {
            statusEl.innerHTML = '<span class="aud-dot aud-dot-' + state + '"></span>';
        }

        function resetRoot() {
            root.innerHTML = '';
            root.className = 'aud-slide-root';
            targetStack = [root];
        }

        function startTimer() {
            if (timerStart) return;
            timerStart = Date.now();
            timerInterval = setInterval(() => {
                const elapsed = Math.floor((Date.now() - timerStart) / 1000);
                const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
                const ss = String(elapsed % 60).padStart(2, '0');
                timerEl.textContent = mm + ':' + ss;
            }, 1000);
        }

        function connect() {
            setStatus('connecting');
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws`);

            ws.onopen = function() {
                setStatus('connected');
                ws.send(JSON.stringify({ type: 'hello', slide: getSlideFromHash() }));
            };

            ws.onmessage = function(event) {
                const msg = JSON.parse(event.data);
                handleMessage(msg);
            };

            ws.onclose = function() {
                setStatus('disconnected');
                setTimeout(connect, 1000);
            };

            ws.onerror = function(err) {
                ws.close();
            };
        }

        function handleMessage(msg) {
            switch (msg.type) {
                case 'mutation':
                    applyMutation(msg);
                    break;
                case 'clear':
                    resetRoot();
                    break;
                case 'slide':
                    startTimer();
                    location.hash = '#slide-' + msg.index;
                    indicator.textContent = msg.total ? (msg.index + 1) + ' / ' + msg.total : String(msg.index + 1);
                    break;
                case 'reload':
                    location.hash = '#slide-' + msg.slide;
                    resetRoot();
                    break;
                case 'notes':
                    notesEl.innerHTML = msg.html || '<em>No notes for this slide.</em>';
                    break;
                case 'next_preview':
                    if (msg.title) {
                        nextTitle.textContent = 'Next: ' + msg.title;
                        nextExcerpt.textContent = msg.excerpt || '';
                    } else {
                        nextTitle.textContent = 'Last slide';
                        nextExcerpt.textContent = '';
                    }
                    break;
                case 'finished':
                    window.__auditorium_finished = true;
                    break;
            }
        }

        function applyMutation(msg) {
            const target = msg.target ? document.querySelector(msg.target) : currentTarget();
            switch (msg.action) {
                case 'append': {
                    const wrapper = document.createElement('div');
                    wrapper.innerHTML = msg.html;
                    const el = wrapper.firstElementChild || wrapper;
                    if (msg.element_id) el.id = msg.element_id;
                    if (target) target.appendChild(el);
                    renderMath(el);
                    renderCode(el);
                    break;
                }
                case 'remove': {
                    const el = document.querySelector(msg.selector);
                    if (el) el.remove();
                    break;
                }
                case 'replace': {
                    const el = document.querySelector(msg.selector);
                    if (el) { el.innerHTML = msg.html; renderMath(el); renderCode(el); }
                    break;
                }
                case 'set_class': {
                    const el = document.querySelector(msg.selector);
                    if (el) el.classList.add(...msg.cls.split(' '));
                    break;
                }
                case 'remove_class': {
                    const el = document.querySelector(msg.selector);
                    if (el) el.classList.remove(...msg.cls.split(' '));
                    break;
                }
                case 'push_target': {
                    const el = document.querySelector(msg.selector);
                    if (el) targetStack.push(el);
                    break;
                }
                case 'pop_target': {
                    if (targetStack.length > 1) targetStack.pop();
                    break;
                }
            }
            if (msg.id && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ack', id: msg.id }));
            }
        }

        function renderMath(el) {
            if (typeof renderMathInElement === 'function') {
                renderMathInElement(el, {
                    delimiters: [
                        { left: '$$', right: '$$', display: true },
                        { left: '$', right: '$', display: false },
                    ],
                    throwOnError: false,
                });
            }
        }

        function renderCode(el) {
            if (typeof hljs !== 'undefined') {
                el.querySelectorAll('pre code').forEach(block => hljs.highlightElement(block));
            }
        }

        document.addEventListener('keydown', function(e) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                const key = e.key;
                if (['ArrowRight', 'ArrowLeft', 'PageDown', ' ', 'r'].includes(key) ||
                    (key >= '0' && key <= '9') || key === 'Enter') {
                    e.preventDefault();
                    ws.send(JSON.stringify({ type: 'keypress', key: key }));
                }
            }
        });

        connect();
    })();
    </script>
</body>
</html>
```

- [ ] **Step 2: Add presenter CSS to theme.css**

Append to `auditorium/static/theme.css`:

```css
/* ---- Presenter view ---- */

#presenter-container {
    display: flex;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
}

#slide-pane {
    flex: 2;
    border-right: 1px solid #e5e7eb;
    overflow: hidden;
}

#slide-pane #slide-root {
    transform: scale(0.75);
    transform-origin: top left;
    width: 133.33%;
    height: 133.33%;
}

#info-pane {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 1.5rem;
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 1rem;
    line-height: 1.6;
    overflow-y: auto;
}

#notes {
    flex: 1;
    overflow-y: auto;
    padding-bottom: 1rem;
    border-bottom: 1px solid #e5e7eb;
    margin-bottom: 1rem;
}

#notes h1, #notes h2, #notes h3 {
    font-family: 'Playfair Display', Georgia, serif;
    font-weight: 600;
}

#next-preview {
    padding-bottom: 1rem;
    border-bottom: 1px solid #e5e7eb;
    margin-bottom: 1rem;
    color: #6b7280;
}

#next-title {
    font-weight: 600;
    margin-bottom: 0.25rem;
}

#next-excerpt {
    font-style: italic;
    font-size: 0.9rem;
}

#presenter-footer {
    display: flex;
    justify-content: space-between;
    font-family: monospace;
    font-size: 0.875rem;
    color: #9ca3af;
}
```

- [ ] **Step 3: Commit**

```bash
git add auditorium/static/presenter.html auditorium/static/theme.css
git commit -m "feat: add presenter view with notes, timer, and next-slide preview"
```

---

### Task 4: Wire up presenter route and keyboard shortcut

**Files:**
- Modify: `auditorium/server.py:77-83` (add `/presenter` route)
- Modify: `auditorium/static/index.html:212-220` (add `p` keypress)
- Modify: `auditorium/cli.py:54-90` (add `--presenter` flag)

- [ ] **Step 1: Add `/presenter` route to server.py**

After the `/` route (line 80), add:

```python
    @app.get("/presenter")
    async def presenter() -> HTMLResponse:
        html = (STATIC_DIR / "presenter.html").read_text()
        return HTMLResponse(html)
```

- [ ] **Step 2: Add `p` keypress to open presenter in index.html**

In `auditorium/static/index.html`, update the keydown handler (line 215) to include `'p'` in the key list, and add a special case before the websocket send:

```javascript
        document.addEventListener('keydown', function(e) {
            if (e.key === 'p') {
                e.preventDefault();
                window.open('/presenter' + location.hash, '_blank');
                return;
            }
            if (ws && ws.readyState === WebSocket.OPEN) {
                const key = e.key;
                if (['ArrowRight', 'ArrowLeft', 'PageDown', ' ', 'r'].includes(key) ||
                    (key >= '0' && key <= '9') || key === 'Enter') {
                    e.preventDefault();
                    ws.send(JSON.stringify({ type: 'keypress', key: key }));
                }
            }
        });
```

- [ ] **Step 3: Add `--presenter` flag to run command**

In `auditorium/cli.py`, add a `presenter` option to the `run` command and open both tabs when enabled:

```python
@app.command()
def run(
    deck_path: Path = typer.Argument(..., help="Path to the deck.py file"),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser automatically"),
    presenter: bool = typer.Option(False, "--presenter", help="Also open presenter view"),
    watch: bool = typer.Option(True, "--watch/--no-watch", help="Watch for file changes and hot-reload"),
) -> None:
```

And update the browser-open logic:

```python
    if open_browser:
        import webbrowser
        import threading

        def _open():
            import time
            time.sleep(0.5)
            webbrowser.open(f"http://{host}:{port}")
            if presenter:
                time.sleep(0.3)
                webbrowser.open(f"http://{host}:{port}/presenter")

        threading.Thread(target=_open, daemon=True).start()
```

- [ ] **Step 4: Commit**

```bash
git add auditorium/server.py auditorium/static/index.html auditorium/cli.py
git commit -m "feat: wire presenter route, p-key shortcut, and --presenter flag"
```

---

### Task 5: Create exporter module (mutation-recording approach)

**Files:**
- Create: `auditorium/exporter.py`

The exporter captures DOM snapshots at each step boundary by intercepting websocket messages. For HTML export, it builds an interactive replay with embedded timing. For PDF/PNG, it renders final or per-step states.

- [ ] **Step 1: Create exporter.py**

```python
from __future__ import annotations

import asyncio
import base64
import shutil
import tempfile
from pathlib import Path

import typer
import uvicorn


async def export_deck(
    deck_path: Path,
    output: Path,
    fmt: str,
    resolution: str,
    port: int,
) -> None:
    """Export a presentation to PDF, HTML, or PNG."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        typer.echo(
            "Export requires playwright. Install with:\n"
            "  pip install auditorium[record]\n"
            "  playwright install chromium",
            err=True,
        )
        raise typer.Exit(1)

    from auditorium.cli import _load_deck
    from auditorium.server import create_app

    deck = _load_deck(deck_path)
    app = create_app(deck)
    total = len(deck.slides)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    while not server.started:
        await asyncio.sleep(0.05)

    width, height = _parse_resolution(resolution)
    tmpdir = tempfile.mkdtemp(prefix="auditorium-export-")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": width, "height": height})

            if fmt == "png":
                output.mkdir(parents=True, exist_ok=True)

            slide_doms = []

            for i in range(total):
                # Navigate to slide i with auto_step=0 (instant) and slide_delay=0 (no linger)
                url = f"http://127.0.0.1:{port}/?auto_step=0&slide_delay=0#slide-{i}"
                await page.goto(url)
                # Wait for the slide to finish (finished signal or next auto-advance)
                await page.wait_for_function(
                    "() => window.__auditorium_finished === true",
                    timeout=60000,
                )
                # Reset the finished flag for the next slide
                await page.evaluate("() => { window.__auditorium_finished = false; }")

                typer.echo(f"  Slide {i + 1}/{total}")

                if fmt == "png":
                    await page.screenshot(path=str(output / f"slide-{i + 1:03d}.png"))
                elif fmt == "html":
                    dom = await page.evaluate("""() => {
                        const root = document.getElementById('slide-root');
                        return {
                            html: root.innerHTML,
                            classes: root.className
                        };
                    }""")
                    slide_doms.append(dom)
                elif fmt == "pdf":
                    dom = await page.evaluate("""() => {
                        const root = document.getElementById('slide-root');
                        return {
                            html: root.innerHTML,
                            classes: root.className
                        };
                    }""")
                    slide_doms.append(dom)

            await browser.close()

        if fmt == "html":
            _build_html(slide_doms, output, width, height)
            typer.echo(f"HTML saved to {output}")
        elif fmt == "pdf":
            await _build_pdf(slide_doms, output, width, height, port, tmpdir)
            typer.echo(f"PDF saved to {output}")
        elif fmt == "png":
            typer.echo(f"PNG slides saved to {output}/")

    finally:
        server.should_exit = True
        await server_task
        shutil.rmtree(tmpdir, ignore_errors=True)


def _build_html(slide_doms: list[dict], output: Path, width: int, height: int) -> None:
    """Build a self-contained HTML file with all slides."""
    # Read theme CSS
    from auditorium.server import STATIC_DIR
    theme_css = (STATIC_DIR / "theme.css").read_text()
    katex_css = (STATIC_DIR / "vendor" / "katex" / "katex.min.css").read_text()

    # Inline fonts as data URLs
    font_dir = STATIC_DIR / "fonts"
    font_faces = ""
    for font_file in font_dir.glob("*.woff2"):
        b64 = base64.b64encode(font_file.read_bytes()).decode()
        name = font_file.stem.replace("-latin", "").replace("-", " ").title()
        font_faces += f"""
@font-face {{
    font-family: '{name}';
    src: url(data:font/woff2;base64,{b64}) format('woff2');
    font-weight: 300 700;
    font-display: block;
}}
"""

    slides_html = ""
    for i, dom in enumerate(slide_doms):
        display = "block" if i == 0 else "none"
        slides_html += f'<div class="export-slide {dom["classes"]}" style="display:{display};">{dom["html"]}</div>\n'

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Exported Presentation</title>
<style>
{font_faces}
{theme_css}
{katex_css}
.export-slide {{
    width: {width}px;
    height: {height}px;
    overflow: hidden;
}}
body {{ margin: 0; background: #fff; overflow: hidden; }}
#counter {{ position: fixed; bottom: 1rem; right: 1rem; font: 0.875rem monospace; color: #9ca3af; }}
</style>
</head>
<body>
{slides_html}
<div id="counter">1 / {len(slide_doms)}</div>
<script>
(function() {{
    const slides = document.querySelectorAll('.export-slide');
    const counter = document.getElementById('counter');
    let current = 0;
    function show(n) {{
        n = Math.max(0, Math.min(n, slides.length - 1));
        slides[current].style.display = 'none';
        slides[n].style.display = 'block';
        current = n;
        counter.textContent = (current + 1) + ' / ' + slides.length;
    }}
    document.addEventListener('keydown', function(e) {{
        if (e.key === 'ArrowRight' || e.key === ' ') {{ e.preventDefault(); show(current + 1); }}
        else if (e.key === 'ArrowLeft') {{ e.preventDefault(); show(current - 1); }}
    }});
}})();
</script>
</body>
</html>""")


async def _build_pdf(slide_doms: list[dict], output: Path, width: int, height: int, port: int, tmpdir: str) -> None:
    """Build a vector PDF by rendering a print-optimized page."""
    from playwright.async_api import async_playwright
    from auditorium.server import STATIC_DIR

    theme_css = (STATIC_DIR / "theme.css").read_text()
    katex_css = (STATIC_DIR / "vendor" / "katex" / "katex.min.css").read_text()

    slides_html = ""
    for i, dom in enumerate(slide_doms):
        pb = "page-break-after: always;" if i < len(slide_doms) - 1 else ""
        slides_html += f'<div class="{dom["classes"]}" style="width:{width}px;height:{height}px;overflow:hidden;{pb}">{dom["html"]}</div>\n'

    print_html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<style>{theme_css}\n{katex_css}\nbody {{ margin: 0; }}</style>
</head><body>{slides_html}</body></html>"""

    html_path = Path(tmpdir) / "print.html"
    html_path.write_text(print_html)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"file://{html_path}")
        await page.wait_for_timeout(1000)
        output.parent.mkdir(parents=True, exist_ok=True)
        await page.pdf(
            path=str(output),
            width=f"{width}px",
            height=f"{height}px",
            print_background=True,
        )
        await browser.close()


def _parse_resolution(resolution: str) -> tuple[int, int]:
    """Parse '1920x1080' into (1920, 1080)."""
    parts = resolution.lower().split("x")
    if len(parts) != 2:
        raise typer.BadParameter(f"Invalid resolution: {resolution}")
    return int(parts[0]), int(parts[1])
```

- [ ] **Step 2: Commit**

```bash
git add auditorium/exporter.py
git commit -m "feat: add exporter module for PDF, HTML, and PNG export"
```

---

### Task 6: Add export CLI command

**Files:**
- Modify: `auditorium/cli.py`

- [ ] **Step 1: Add the export command**

Add after the `record` command in `auditorium/cli.py`:

```python
@app.command()
def export(
    deck_path: Path = typer.Argument(..., help="Path to the deck.py file"),
    fmt: str = typer.Option("pdf", "-f", "--format", help="Output format: pdf, html, png"),
    output: Path = typer.Option(None, "-o", "--output", help="Output path (default: deck.pdf/html or slides/)"),
    resolution: str = typer.Option("1920x1080", help="Viewport size, e.g. 1280x720"),
    step_by_step: bool = typer.Option(False, "--step-by-step", help="One page/frame per step instead of per slide"),
    port: int = typer.Option(0, help="Server port (0 = random)"),
) -> None:
    """Export presentation to PDF, HTML, or PNG."""
    deck_path = deck_path.resolve()
    if not deck_path.exists():
        typer.echo(f"Error: {deck_path} not found", err=True)
        raise typer.Exit(1)

    if fmt not in ("pdf", "html", "png"):
        typer.echo(f"Error: unknown format '{fmt}'. Use pdf, html, or png.", err=True)
        raise typer.Exit(1)

    if output is None:
        stem = deck_path.stem
        if fmt == "png":
            output = Path(f"{stem}-slides")
        else:
            output = Path(f"{stem}.{fmt}")

    if port == 0:
        import socket
        with socket.socket() as s:
            s.bind(("", 0))
            port = s.getsockname()[1]

    from auditorium.exporter import export_deck
    typer.echo(f"Exporting to {fmt}...")
    asyncio.run(export_deck(deck_path, output, fmt, resolution, step_by_step, port))
```

- [ ] **Step 2: Verify CLI help**

```bash
uv run auditorium export --help
```

Expected: shows export command with --format, --output, --resolution options.

- [ ] **Step 3: Commit**

```bash
git add auditorium/cli.py
git commit -m "feat: add 'auditorium export' CLI command"
```

---

### Task 7: Version bump + docs

**Files:**
- Modify: `pyproject.toml` (version → `1!3.0.0`)
- Modify: `auditorium/cli.py:17` (version string)
- Modify: `Readme.md`
- Modify: `CHANGELOG.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Bump version**

In `pyproject.toml`: `version = "1!3.0.0"`
In `auditorium/cli.py`: `typer.echo("auditorium 1!3.0.0")`

- [ ] **Step 2: Update CHANGELOG.md**

Add at the top:

```markdown
## 3.0.0

### Breaking

- **Docstrings are now presenter notes**, not slide content. All visible content must come from `md()`, `show()`, etc. in the function body. Docstrings are shown only in the presenter view.

### Added

- **Presenter mode** — press `p` or use `--presenter` flag to open a second tab with notes, elapsed timer, current slide mirror, and next-slide preview.
- **`auditorium export`** — export presentations to PDF (vector), self-contained HTML (arrow-key navigator), or PNG (one image per slide). Requires `auditorium[record]`.
- `/presenter` route serves the presenter view HTML.

### Changed

- `demo_deck.py` rewritten: all content via `md()` calls, docstrings are presenter notes.
```

- [ ] **Step 3: Update Readme.md**

Add a `## Presenter Mode` section after `## Navigation` and update the `## Recording` section to mention export. Update the code example to not use docstring content.

- [ ] **Step 4: Update CLAUDE.md**

Add `presenter.html` and `exporter.py` to the key modules list.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml auditorium/cli.py Readme.md CHANGELOG.md CLAUDE.md
git commit -m "docs: v3.0.0 version bump, changelog, and documentation updates"
```

---

### Task 8: End-to-end testing

- [ ] **Step 1: Test presenter view**

```bash
uv run auditorium run examples/demo_deck.py --no-open --port 8790 &
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8790/presenter
# Expected: 200
kill $(lsof -t -i:8790) 2>/dev/null
```

- [ ] **Step 2: Test HTML export**

```bash
uv run auditorium export examples/demo_deck.py -f html -o /tmp/test-export.html
# Expected: produces self-contained HTML file
ls -lh /tmp/test-export.html
```

- [ ] **Step 3: Test PDF export**

```bash
uv run auditorium export examples/demo_deck.py -f pdf -o /tmp/test-export.pdf
ls -lh /tmp/test-export.pdf
file /tmp/test-export.pdf
# Expected: PDF document
```

- [ ] **Step 4: Test PNG export**

```bash
uv run auditorium export examples/demo_deck.py -f png -o /tmp/test-slides/
ls /tmp/test-slides/
# Expected: slide-001.png through slide-011.png
```

- [ ] **Step 5: Clean up and commit**

```bash
rm -rf /tmp/test-export.html /tmp/test-export.pdf /tmp/test-slides/
```
