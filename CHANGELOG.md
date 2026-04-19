# Changelog

## 3.1.0

### Added

- **Video recording** (`auditorium record`) with Rich progress bars and ETA.
- **Step-by-step export** (`--step-by-step`) — captures one frame per `step()` and `sleep()` boundary, not just final slide state.
- **Timed auto-advance in HTML export** — sleep boundaries auto-play at their authored duration, step boundaries wait for keypress, matching the live presentation behavior.
- **Live session status** — `auditorium run` shows a Rich Live table of connected sessions with current slide and task status.
- **Connection status dot** — green/red/blinking orange indicator in bottom-left of presentation.
- **Rich CLI output** — startup banner panel, styled progress bars, colored messages.

### Fixed

- Export now waits for `slide_complete` signal instead of fixed timeout, fixing slides with `sleep()` that were captured mid-animation.
- Animations disabled during export (CSS `animation-duration: 0s !important`) — no more half-faded screenshots.
- `sleep()` is instant in export mode (`instant_sleep` flag) — exports are fast regardless of authored timings.
- KaTeX fonts fully inlined as base64 in HTML/PDF exports — no 404s for math fonts.
- Left arrow in exported step-by-step HTML goes to previous slide (consistent with live mode), not previous step.
- Step-by-step export uses keypress-driven capture (one run per slide) instead of fragile re-run approach.

### Changed

- Replaced tqdm with Rich for all CLI progress output.
- All assets bundled locally — zero CDN dependencies, fully offline presentations.
- Per-client sessions — each browser tab runs independently on the server.

## 3.0.0

### Breaking

- **Docstrings are now presenter notes**, not slide content. All visible content must come from `md()`, `show()`, etc. in the function body. Docstrings are shown only in the presenter view.

### Added

- **Presenter mode** — press `p` or use `--presenter` flag to open a second tab with notes, elapsed timer, current slide mirror, and next-slide preview. Also available at `/presenter`.
- **`auditorium export`** — export presentations to PDF (vector), self-contained HTML (arrow-key navigator), or PNG (one image per slide). Requires `auditorium[record]`.

### Changed

- `demo_deck.py` rewritten: all content via `md()` calls, docstrings are presenter notes.

## 2.1.0

### Added

- **Video recording** (`auditorium record`) — capture presentations to `.webm` video via Playwright. Two modes: auto (headless, deterministic pacing with `--auto-step` and `--slide-delay`) and live (visible browser, you drive with keypresses). Install with `pip install auditorium[record]`.
- **Fully offline** — all assets (KaTeX, highlight.js, fonts) are bundled in the package. Zero outbound requests. Presentations work without internet.
- **Per-client sessions** — each browser tab runs its own independent slide session on the server. Keypresses in one tab don't affect others.
- **Connection status indicator** — small dot in the bottom-left corner: green (connected), red (disconnected), blinking orange (reconnecting).
- **Graceful reconnection** — client auto-reconnects after server restarts and resumes at the same slide. No manual browser refresh needed.
- **`"auto"` layout sizing** — `rows()` and `columns()` accept `"auto"` in sizing lists for natural-size regions. `rows(["auto", 1, "auto"])` creates a header/body/footer layout where the body stretches.
- **FLIP animations** — existing content smoothly repositions when new elements are added, instead of snapping.

### Changed

- Dropped Tailwind CSS CDN — replaced with plain CSS. No external runtime dependencies.
- Dropped Google Fonts CDN — Playfair Display and Source Serif 4 are vendored as woff2 files with `font-display: block`.
- Dropped `stable_top()` — replaced by the more general `rows(["auto", 1])` pattern.
- Server architecture changed from shared state to per-session `Session` dataclass.
- Clean shutdown on Ctrl+C (fixed `FATAL: exception not rethrown` crash).

### Fixed

- Flexbox layouts (header/body/footer) now correctly pin to top/bottom of the viewport.
- Elements inside layout regions now animate on entry (previously only direct children of slide root animated).

## 2.0.1

- Added README to PyPI metadata.

## 2.0.0

- Ground-up rewrite. Server-driven slide framework with FastAPI + WebSocket.
- Slides as `async def` functions with `@deck.slide` decorator.
- Async vocabulary: `show`, `hide`, `replace`, `set_class`, `remove_class`, `md`, `show_md`, `step`, `sleep`.
- Layout primitives: `columns`, `rows`, `place`.
- CLI: `auditorium run deck.py` with hot reload and auto-browser-open.
- Academic-serif theme with Playfair Display + Source Serif 4.
- Navigation: forward/back/restart/jump with keyboard.
- Example deck: `examples/demo_deck.py`.
