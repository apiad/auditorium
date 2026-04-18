# Video Recording Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `auditorium record deck.py` to produce mp4/webm videos of presentations using Playwright.

**Architecture:** The server gets a `auto_step` field on `Session` so `step()` auto-advances after a timeout. A new `recorder.py` module starts the server programmatically, launches Playwright, and captures the video. The CLI gets a `record` command.

**Tech Stack:** Playwright (optional dep via `auditorium[record]`), uvicorn (programmatic server), existing FastAPI app.

---

### File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `pyproject.toml` | Modify | Add `record` optional dependency |
| `auditorium/server.py:19-28` | Modify | Add `auto_step` field to `Session` |
| `auditorium/server.py:126-147` | Modify | Send `finished` message after last slide |
| `auditorium/slide.py:82-86` | Modify | Auto-advance `step()` when `auto_step` is set |
| `auditorium/server.py:90-95` | Modify | Parse `auto_step` from `hello` message |
| `auditorium/recorder.py` | Create | Recording logic: start server, launch Playwright, capture video |
| `auditorium/cli.py` | Modify | Add `record` command |
| `auditorium/static/index.html` | Modify | Send `auto_step` from hello if present in URL params |

---

### Task 1: Add `auto_step` to Session and hello handshake

**Files:**
- Modify: `auditorium/server.py:19-28` (Session dataclass)
- Modify: `auditorium/server.py:90-95` (hello handler)

- [ ] **Step 1: Add `auto_step` field to `Session`**

In `auditorium/server.py`, add to the `Session` dataclass after line 27:

```python
auto_step: float | None = None
```

- [ ] **Step 2: Parse `auto_step` from hello message**

In `auditorium/server.py`, update the hello handler (line 94-95) to:

```python
if msg.get("type") == "hello":
    session.current_slide = msg.get("slide", 0)
    auto_step = msg.get("auto_step")
    if auto_step is not None:
        session.auto_step = float(auto_step)
```

- [ ] **Step 3: Commit**

```bash
git add auditorium/server.py
git commit -m "feat: add auto_step field to Session for recording support"
```

---

### Task 2: Auto-advance `step()` when `auto_step` is set

**Files:**
- Modify: `auditorium/slide.py:82-86`

- [ ] **Step 1: Update `step()` to support auto-advance**

Replace `auditorium/slide.py` lines 82-86 with:

```python
async def step(self) -> None:
    """Wait for a keypress to continue, or auto-advance if auto_step is set."""
    event = asyncio.Event()
    self._session.step_event = event
    if self._session.auto_step is not None:
        try:
            await asyncio.wait_for(event.wait(), timeout=self._session.auto_step)
        except asyncio.TimeoutError:
            pass  # auto-advance
    else:
        await event.wait()
```

- [ ] **Step 2: Verify with manual test**

Start the server, connect a websocket client that sends `auto_step: 1.0` in hello, confirm that `step()` auto-advances after 1 second without any keypress.

```bash
uv run python -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://127.0.0.1:8000/ws') as ws:
        await ws.send(json.dumps({'type': 'hello', 'slide': 1, 'auto_step': 1.0}))
        import time; start = time.time()
        msgs = []
        while time.time() - start < 10:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                if msg.get('id'): await ws.send(json.dumps({'type': 'ack', 'id': msg['id']}))
                msgs.append(msg)
            except asyncio.TimeoutError: break
        muts = sum(1 for m in msgs if m.get('type') == 'mutation')
        print(f'{muts} mutations received (should be >1 if steps auto-advanced)')
asyncio.run(test())
"
```

- [ ] **Step 3: Commit**

```bash
git add auditorium/slide.py
git commit -m "feat: auto-advance step() when session has auto_step timeout"
```

---

### Task 3: Send `finished` message after last slide

**Files:**
- Modify: `auditorium/server.py:126-147` (`_run_slide`)
- Modify: `auditorium/server.py:180-188` (`_go_to_slide`)

- [ ] **Step 1: Send `finished` when the last slide completes naturally**

In `_run_slide`, after the slide function returns successfully (not cancelled), check if this was the last slide and send a `finished` message. Replace `_run_slide` with:

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
        from auditorium.slide import SlideContext

        ctx = SlideContext(session)
        if slide_fn.func.__doc__:
            await ctx.md(slide_fn.func.__doc__)
        await slide_fn.func(ctx)
        # If this was the last slide and it completed naturally, signal finished
        if index == len(deck.slides) - 1:
            await session.send({"type": "finished"})
    except (asyncio.CancelledError, Exception):
        pass
```

- [ ] **Step 2: Auto-advance to next slide in auto_step mode**

In `_go_to_slide`, after the slide task completes in auto mode, automatically advance to the next slide. Actually, this is better handled differently: when a slide function returns normally (not the last slide), the session should auto-advance to the next slide if `auto_step` is set.

Add to the end of `_run_slide`, inside the try block, after the slide function call and before the finished check:

```python
        await slide_fn.func(ctx)
        # Auto-advance to next slide if in recording mode
        if session.auto_step is not None and index < len(deck.slides) - 1:
            session.current_slide = index + 1
            session.slide_task = asyncio.create_task(_run_slide(app, session))
            return
        # If this was the last slide and it completed naturally, signal finished
        if index == len(deck.slides) - 1:
            await session.send({"type": "finished"})
```

- [ ] **Step 3: Commit**

```bash
git add auditorium/server.py
git commit -m "feat: auto-advance slides and send finished signal in recording mode"
```

---

### Task 4: Add `record` optional dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add record extras**

In `pyproject.toml`, update `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
record = ["playwright>=1.40"]
dev = [
    "pytest>=8",
    "ruff>=0.4",
]
```

- [ ] **Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add playwright as optional dependency for recording"
```

---

### Task 5: Create `recorder.py`

**Files:**
- Create: `auditorium/recorder.py`

- [ ] **Step 1: Write the recorder module**

Create `auditorium/recorder.py`:

```python
from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

import typer
import uvicorn


async def record(
    deck_path: Path,
    output: Path,
    resolution: str,
    auto_step: float,
    live: bool,
    port: int,
) -> None:
    """Record a presentation to video."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        typer.echo(
            "Recording requires playwright. Install with:\n"
            "  pip install auditorium[record]\n"
            "  playwright install chromium",
            err=True,
        )
        raise typer.Exit(1)

    from auditorium.cli import _load_deck
    from auditorium.server import create_app

    # Load deck and create app
    deck = _load_deck(deck_path)
    app = create_app(deck)

    # Start uvicorn programmatically
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    # Wait for server to start
    while not server.started:
        await asyncio.sleep(0.05)

    width, height = _parse_resolution(resolution)
    tmpdir = tempfile.mkdtemp(prefix="auditorium-record-")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not live)
            context = await browser.new_context(
                viewport={"width": width, "height": height},
                record_video_dir=tmpdir,
                record_video_size={"width": width, "height": height},
            )
            page = await context.new_page()
            url = f"http://127.0.0.1:{port}/"
            if not live:
                url += f"?auto_step={auto_step}"
            await page.goto(url)

            if live:
                typer.echo(f"Recording live. Navigate with keypresses. Close the browser to stop.")
                await page.wait_for_event("close", timeout=0)
            else:
                typer.echo(f"Recording {len(deck.slides)} slides with {auto_step}s per step...")
                # Wait for the "finished" message via the page's console
                await page.wait_for_function(
                    "() => window.__auditorium_finished === true",
                    timeout=len(deck.slides) * 60 * 1000,  # generous timeout
                )
                typer.echo("All slides recorded.")

            await context.close()
            await browser.close()

        # Find the recorded video and move it to the output path
        video_files = list(Path(tmpdir).glob("*.webm"))
        if video_files:
            src = video_files[0]
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(output))
            typer.echo(f"Video saved to {output}")
        else:
            typer.echo("Error: no video file produced", err=True)
    finally:
        server.should_exit = True
        await server_task
        shutil.rmtree(tmpdir, ignore_errors=True)


def _parse_resolution(resolution: str) -> tuple[int, int]:
    """Parse '1920x1080' into (1920, 1080)."""
    parts = resolution.lower().split("x")
    if len(parts) != 2:
        raise typer.BadParameter(f"Invalid resolution: {resolution}. Use WIDTHxHEIGHT, e.g. 1920x1080")
    return int(parts[0]), int(parts[1])
```

- [ ] **Step 2: Commit**

```bash
git add auditorium/recorder.py
git commit -m "feat: add recorder module for video capture via Playwright"
```

---

### Task 6: Update client to handle `auto_step` and `finished`

**Files:**
- Modify: `auditorium/static/index.html`

- [ ] **Step 1: Pass `auto_step` in hello message from URL params**

In `auditorium/static/index.html`, update the `ws.onopen` handler to read `auto_step` from URL query params and include it in the hello message. Replace the `onopen` handler:

```javascript
ws.onopen = function() {
    setStatus('connected');
    // Send hello with current slide from hash and optional auto_step from URL params
    const params = new URLSearchParams(location.search);
    const hello = { type: 'hello', slide: getSlideFromHash() };
    const autoStep = params.get('auto_step');
    if (autoStep) hello.auto_step = parseFloat(autoStep);
    ws.send(JSON.stringify(hello));
};
```

- [ ] **Step 2: Handle `finished` message**

In the `handleMessage` function, add a case for `finished`:

```javascript
case 'finished':
    window.__auditorium_finished = true;
    break;
```

- [ ] **Step 3: Commit**

```bash
git add auditorium/static/index.html
git commit -m "feat: client support for auto_step param and finished signal"
```

---

### Task 7: Add `record` CLI command

**Files:**
- Modify: `auditorium/cli.py`

- [ ] **Step 1: Add the record command**

Add after the `run` command in `auditorium/cli.py`:

```python
@app.command()
def record(
    deck_path: Path = typer.Argument(..., help="Path to the deck.py file"),
    output: Path = typer.Option("recording.webm", "-o", "--output", help="Output file path"),
    resolution: str = typer.Option("1920x1080", help="Viewport size, e.g. 1280x720"),
    auto_step: float = typer.Option(2.0, "--auto-step", help="Seconds per step() in auto mode"),
    live: bool = typer.Option(False, "--live", help="Launch visible browser for manual recording"),
    port: int = typer.Option(0, help="Server port (0 = random)"),
) -> None:
    """Record a presentation to video."""
    deck_path = deck_path.resolve()
    if not deck_path.exists():
        typer.echo(f"Error: {deck_path} not found", err=True)
        raise typer.Exit(1)

    if port == 0:
        import socket
        with socket.socket() as s:
            s.bind(("", 0))
            port = s.getsockname()[1]

    from auditorium.recorder import record as do_record
    asyncio.run(do_record(deck_path, output, resolution, auto_step, live, port))
```

- [ ] **Step 2: Commit**

```bash
git add auditorium/cli.py
git commit -m "feat: add 'auditorium record' CLI command"
```

---

### Task 8: End-to-end test

- [ ] **Step 1: Install playwright and chromium**

```bash
uv add --optional record playwright
uv run playwright install chromium
```

- [ ] **Step 2: Test auto mode**

```bash
uv run auditorium record examples/demo_deck.py -o test-auto.webm --auto-step 1.0
```

Expected: produces `test-auto.webm` with all 11 slides, each step pausing ~1s. File exists and plays.

- [ ] **Step 3: Test live mode**

```bash
uv run auditorium record examples/demo_deck.py -o test-live.webm --live
```

Expected: Chrome opens, you navigate manually, close browser, `test-live.webm` saved.

- [ ] **Step 4: Test custom resolution**

```bash
uv run auditorium record examples/demo_deck.py -o test-720p.webm --resolution 1280x720 --auto-step 0.5
```

Expected: smaller viewport video.

- [ ] **Step 5: Test without playwright installed**

```bash
uv run python -c "from auditorium.recorder import record" 2>&1 || true
```

Expected: ImportError is handled gracefully at runtime, not at import time.

- [ ] **Step 6: Clean up test files and commit**

```bash
rm -f test-auto.webm test-live.webm test-720p.webm
git add -A
git commit -m "feat: video recording v2.1 complete"
```

---

### Task 9: Update docs

**Files:**
- Modify: `Readme.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add recording section to README**

Add a `## Recording` section after `## Features` in `Readme.md`:

```markdown
## Recording

Record your presentation to video (requires `pip install auditorium[record]` and `playwright install chromium`):

```bash
# Auto mode: headless, deterministic pacing
auditorium record talk.py -o talk.webm --auto-step 2.0

# Live mode: you drive, Playwright captures
auditorium record talk.py -o talk.webm --live
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--output` / `-o` | `recording.webm` | Output file path |
| `--resolution` | `1920x1080` | Viewport size |
| `--auto-step` | `2.0` | Seconds per `step()` in auto mode |
| `--live` | off | Visible browser, manual navigation |
```

- [ ] **Step 2: Update CLAUDE.md architecture section**

Add `recorder.py` to the key modules list in `CLAUDE.md`.

- [ ] **Step 3: Commit**

```bash
git add Readme.md CLAUDE.md
git commit -m "docs: add recording section to README and CLAUDE.md"
```
