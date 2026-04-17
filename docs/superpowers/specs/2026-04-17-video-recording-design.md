# Video Recording (`auditorium record`)

## Problem

Auditorium presentations are live-only. To share a talk, you share the repo and run instructions. There's no way to produce a video artifact for YouTube, documentation, or asynchronous viewing.

## Solution

Add `auditorium record deck.py` as a CLI command that uses Playwright to drive the presentation in a browser and capture it as a video file. Two modes: auto (headless, deterministic pacing) and live (headed, human-driven).

## CLI Interface

```
auditorium record deck.py [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output` / `-o` | `recording.mp4` | Output path. Format from extension: `.mp4`, `.webm` |
| `--resolution` | `1920x1080` | Viewport size, e.g. `1280x720`, `3840x2160` |
| `--auto-step` | `2.0` | Seconds each `step()` pauses before auto-advancing |
| `--live` | off | Launch visible browser; you drive with keypresses |
| `--port` | `0` (random) | Internal server port |

### Auto mode (default)

Headless Playwright. The recorder starts the server, connects a browser, and walks every slide automatically. Each `step()` pauses for `--auto-step` seconds then self-resolves. `sleep()` runs at its authored duration. The result is a deterministic video with consistent pacing.

The recording stops when the last slide's function returns.

### Live mode (`--live`)

Headed Playwright (visible Chrome window). You present with keypresses as in a normal talk. Playwright records the window. Recording stops when you close the browser or press `q`.

## Architecture

### New module: `auditorium/recorder.py`

Single public function: `record(deck_path, output, resolution, auto_step, live, port)`.

Flow:
1. Load the deck module via `_load_deck()` (reuse from `cli.py`).
2. Create the FastAPI app via `create_app(deck)`.
3. Start uvicorn programmatically using `uvicorn.Server(config)` in an asyncio task (not `uvicorn.run()`, which blocks).
4. Launch Playwright browser — `chromium.launch(headless=not live)`.
5. Create a browser context with `record_video={"dir": tmpdir, "size": resolution}`.
6. Open a page, navigate to `http://localhost:{port}/`.
7. The page's JS sends `{"type": "hello", "slide": 0, "auto_step": auto_step}` (auto mode) or `{"type": "hello", "slide": 0}` (live mode).
8. Wait for completion:
   - Auto mode: poll the session until `slide_task` is done and `current_slide == last_slide`. Or: the server sends a `{"type": "finished"}` message when the last slide function returns.
   - Live mode: wait for the browser to close (`page.wait_for_event("close")`).
9. Close the browser context (Playwright finalizes the video to `tmpdir`).
10. Move the video file from `tmpdir` to `--output` path.
11. Shut down the uvicorn server.

### Server changes: auto-step support

The `hello` message gains an optional `auto_step` field:

```json
{"type": "hello", "slide": 0, "auto_step": 2.0}
```

When `auto_step` is set on a `Session`, it's stored as `session.auto_step: float | None`.

**`SlideContext.step()` change:**

```python
async def step(self) -> None:
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

This is session-scoped: a recording session auto-advances while a live browser tab in another window still waits for keypresses.

**End-of-deck signal:**

When `_run_slide` finishes the last slide (function returns, not cancelled), the server sends `{"type": "finished"}` to the session. The recorder watches for this message to know when to stop.

### CLI integration

Add `record` as a new Typer command in `cli.py`. It imports `recorder.record()` and calls it. At the top of `record()`, check for Playwright:

```python
try:
    from playwright.async_api import async_playwright
except ImportError:
    typer.echo("Recording requires playwright. Install with: pip install auditorium[record]", err=True)
    raise typer.Exit(1)
```

### Dependency

In `pyproject.toml`:

```toml
[project.optional-dependencies]
record = ["playwright>=1.40"]
dev = ["pytest>=8", "ruff>=0.4"]
```

Playwright browser binaries are installed separately via `playwright install chromium` after pip install. The `record` command should check for this and print a helpful message if missing.

## What's NOT in scope

- Editing/trimming the video (use ffmpeg or a video editor)
- Slide transitions or cross-fade effects (CSS handles transitions already)
- Audio narration capture (possible future extension)
- GIF output (convert from mp4 with ffmpeg)
- Presenter notes overlay in the video

## Verification

1. `uv run auditorium record examples/demo_deck.py -o test.mp4` — produces an mp4 of all 11 slides
2. `uv run auditorium record examples/demo_deck.py --live -o live.mp4` — opens Chrome, manual navigation, video saved on close
3. `uv run auditorium record examples/demo_deck.py --resolution 1280x720 --auto-step 1.0 -o fast.mp4` — smaller, faster video
4. Running `auditorium record` without `playwright` installed gives a clear error message
5. While recording in auto mode, opening a regular browser tab works independently
