# Changelog

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
