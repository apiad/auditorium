# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Auditorium 2.0 is a server-driven Python presentation framework. Slides are `async def` functions decorated with `@deck.slide`. A FastAPI server runs slide functions and pushes DOM mutations over WebSocket to a minimal HTML client. The client is dumb: it receives mutations and applies them.

## Commands

```bash
uv sync                                    # install dependencies
uv run auditorium run examples/demo_deck.py  # run the demo presentation
uv run auditorium run deck.py --no-open    # run without auto-opening browser
uv run auditorium render deck.py -o out.mp4  # render to video, frame by frame
uv run pytest                              # run tests (103 passing)
uv run ruff check auditorium/              # lint
```

## Architecture

Each browser tab gets its own `Session` on the server with independent slide state. The client is a static HTML page with a small JS module that applies mutations, captures keypresses, and acks.

**Request flow:** Client connects via WebSocket and sends `{"type": "hello", "slide": N}` -> server creates a `Session` and starts the slide -> slide function sends `{"type": "mutation"}` -> client applies DOM change and sends `{"type": "ack"}` -> server continues. User keypress -> client sends `{"type": "keypress"}` -> server resolves a `step()` await or navigates slides for that session only.

**Key modules:**

- `server.py` — FastAPI app, `Session` dataclass (per-client state: ws, slide_task, current_slide, step_event, pending_acks), WebSocket endpoint, navigation state machine. Each session has its own `send()` and `send_mutation()` (awaits ack). `reload_deck()` iterates all sessions.
- `deck.py` — `Deck` class with `@slide` decorator. Slides ordered by registration order, overridable with `order=N`. No `run()` method; the CLI owns the server lifecycle.
- `slide.py` — `SlideContext` passed to each slide function. Takes a `Session` (not the app). Exposes the async vocabulary (`show`, `hide`, `replace`, `set_class`, `remove_class`, `md`, `show_md`, `step`, `sleep`) and layout methods (`columns`, `rows`, `place`). Maintains `_target_stack` for layout region scoping. Layout sizing accepts ints (proportional) or `"auto"` (natural size) — e.g. `rows(["auto", 1, "auto"])` for header/body/footer.
- `layout.py` — `Region` (async context manager for `with` block scoping), layout factory functions. Top-level layouts auto-remove `justify-center` from `#slide-root` to switch from centered to fill mode.
- `cli.py` — Typer CLI. `auditorium run <deck.py>` loads the module, discovers the `Deck` instance, sets up file watching (watchfiles), and starts uvicorn. `auditorium record <deck.py>` records to video via Playwright. SIGINT is set to SIG_DFL for clean shutdown.
- `render.py` — Frame-stepped video rendering, the fourth consumer of `seek(t)`. `render_schedule()` is a pure function mapping each output frame to a timeline position (inserting beat dwells), so the frame plan is testable without a browser. `render_frames()` captures PNGs through `window.__auditoriumShow` — never `AuditoriumEngine.seek` directly, because the client autoplays on load and would race the capture. `render_video()` encodes via ffmpeg. Takes `--from`/`--to`, so parallel rendering is a shell-level fan-out. Replaced `recorder.py`, which screen-captured a live browser and was nondeterministic.
- `exporter.py` — Static export to self-contained HTML or PNG stills. **No PDF**: a timeline has no canonical instant to print, so the format was removed in 4.0 rather than guessed at. See Readme.md. Drives by seeking to each beat (Playwright + ephemeral uvicorn). For HTML: inlines all assets into a single file. For PNG: one still per beat. Optional dep: `auditorium[record]`.
- `static/index.html` — HTML shell with Tailwind CDN, KaTeX CDN, highlight.js CDN, Google Fonts. Client-side JS handles WebSocket, `hello` handshake with slide index from URL hash, mutation application (with FLIP animation), keypress capture, auto-reconnect, and connection status dot.
- `static/presenter.html` — Presenter view served at `/presenter`. Shows current slide mirror, speaker notes (from docstring), next-slide preview, and elapsed timer. Syncs with the audience view via a shared session over WebSocket. Opens automatically with `--presenter` flag or press `p` during a presentation.

**Design decisions:** See `design.md` for the full rationale. Key ones: no reveal.js, no build step, server-driven (not Pyodide), flexbox-first layout, `async def` slides with markdown docstrings.

## Releasing

Version uses PEP 440 epoch (`1!2.0.0`) because old PyPI releases used calver (`20.2.1`). The `1!` prefix ensures semver versions sort higher. Keep the `1!` prefix in `pyproject.toml`.

To release, push to main and create a GitHub release:

```bash
git push origin main
gh release create v2.1.0 --title "v2.1.0" --generate-notes
```

The `deploy.yaml` workflow triggers on `release: published` and publishes to PyPI via trusted publisher (no API tokens). Update the version in `pyproject.toml` and `cli.py` before creating the release.

## Living documentation

`examples/demo_deck.py` is living documentation. It must always contain every feature in a sensible structure and run smoothly. When adding a new vocabulary primitive or capability, add a slide to `demo_deck.py` that exercises it. When changing existing behavior, update the relevant slide. Run it (`uv run auditorium run examples/demo_deck.py`) and walk through all slides to verify before considering work complete.
