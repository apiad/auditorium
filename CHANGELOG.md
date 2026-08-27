# Changelog

## 4.0.0b1

### Added

- **`auditorium render`** — deterministic frame-stepped video. Seeks the
  compiled timeline to each frame's position, screenshots, and encodes with
  ffmpeg. Two renders of the same deck are byte-identical. Supports `--fps`,
  `--size` (`1080p`/`720p`/`vertical`/`square` or `WIDTHxHEIGHT`), `--format`
  (`mp4`/`webm`/`png-sequence`), `--audio`, and `--from`/`--to`.
- **Frame ranges** — `--from`/`--to` render a slice, and a worker replays
  forward from frame 0 without capturing so its output matches a sequential
  render exactly. Parallel rendering is a shell-level fan-out plus `concat`.
- **Audio bed** — `deck.audio(path, at=0.0)`, mixed at the ffmpeg step and
  truncated to the video with `-shortest`. Not part of the timeline's visual
  state: `seek()` ignores it and interactive playback stays silent.

### Removed

- **`auditorium record`.** It screen-captured a live browser through
  Playwright's `record_video_dir`, so output depended on machine load. It had
  also been broken since the 4.0 runtime landed. `render` replaces it.

- **PDF export.** A deck is now a timeline, and a scene is a continuous
  function of time, so there is no canonical instant to print. Every candidate
  rule invents semantics the model does not have: end-of-scene loses every
  build stage, one-page-per-pause emits runs of near-identical cumulative
  pages, and author-declared capture points are a knob nobody turns. `png` and
  `html` export survive because both are total functions of the timeline.
  Export stills and assemble them (`img2pdf slides/*.png`), or author print
  documents in a document engine built for pagination.

### Fixed

- **`auditorium export` no longer hangs.** It drove the deck with
  `?instant_sleep=1&auto_step=0` query parameters the 4.0 server does not
  parse, then waited forever on a flag the 4.0 client never sets. It now seeks
  to each beat.
- **`move_to()` actually moves.** It emits `transform.x` and `transform.y`,
  two animations writing one CSS property; under WAAPI's default
  `composite: "replace"` the second won outright and the element never moved.
  Transform tracks now composite additively (opacity deliberately does not —
  additive opacity clamps and would break every fade).
- **Chrome survives `t=0`.** `seek()` pins every animation on the page to
  timeline time, so an entrance animation on the slide indicator sat at its
  first keyframe at `t=0` and vanished from frame 0 of every render.

### Known broken

- **Presenter view (`--presenter`).** Still speaks the pre-4.0 mutation
  protocol; renders nothing. Being rebuilt as a third client over the
  timeline. This is why 4.0 is tagged beta.


## 3.6.0

### Added

- **Six more theme presets**, expanding both axes:
  - layout: `minimalist`, `magazine`, `terminal`
  - color: `solarized`, `pastel`, `mono`
- **Slide transitions** — CSS-only, theme-declared. Each theme can set `--aud-transition` to one of `aud-fade`, `aud-slide-left`, `aud-slide-up`, `aud-zoom`, or `none`. Overridable per-deck with `Deck(transition="fade")` or per-run with `--transition fade`. The client toggles `.aud-slide-enter` on `#slide-root` after each `clear` event; a reflow dance guarantees the animation re-fires on every slide.
- **Section dividers** — `ctx.section("Name", number="01")` renders a large centred title (with optional number above) for slide-level chapter breaks. Themes can hook `.aud-section-divider` / `.aud-section-number` / `.aud-section-title` for custom decoration.
- **Showcase decks** in `examples/showcase/` — seven short combos each exhibiting one layout × one colour theme. Rendered to `docs/examples/*.html` and published to GitHub Pages.
- Expanded `examples/demo_deck.py` into a sectioned tour: Intro / Layouts / Animations / Blocks / Typography / Themes.

## 3.5.0

### Added

- **Semantic title primitives** — `ctx.title("…")` / `ctx.subtitle("…")` render an `<h1 class="aud-slide-title">` / `<h2 class="aud-slide-subtitle">`. Themes can target these for chrome, running heads, or decorations without parsing markdown.
- **Information & academic blocks** — `ctx.block(kind, body_md, *, title=None)` renders a styled callout with a coloured left border and tinted title bar. Kinds:
  - generic: `note`, `info`, `success`, `warning`, `error`, `tip`
  - academic: `definition`, `theorem`, `lemma`, `corollary`, `proof`, `example`, `remark`, `quote`
- Demo deck (`examples/demo_deck.py`) updated with `info_blocks` and `academic_blocks` slides.
- **Stackable themes** — `Deck(theme=...)` and `--theme` accept either a single value or a list and compose orthogonally. Two axes shipped:
  - **layout/typography**: `simple`, `academic`, `comic`, `compact`
  - **color/transitions**: `light`, `dark`, `neon`, `print`
  Values are looked up under `auditorium/themes/<name>.css` or treated as a filesystem path. Resolved CSS is concatenated in declaration order; later entries override earlier via standard cascade. CLI `--theme` (repeatable) **replaces** the deck's `theme=` list entirely so any base can be swapped at runtime.
- **Theme chrome slots** — the HTML shell now carries empty `.aud-chrome-header`, `.aud-chrome-footer`, `.aud-chrome-left`, `.aud-chrome-right` fixed-position regions that themes fill via `::before`/`::after content:`. Themes can read `--aud-deck-title`, `--aud-slide-name`, `--aud-slide-number`, `--aud-slide-total` CSS custom properties (the last three are updated live on every slide change), so chrome content stays purely CSS-driven.

## 3.4.0

### Added

- **Jupyter display protocol** — `ctx.show(obj)` now accepts any object that implements `_repr_html_`, `_repr_svg_`, `_repr_png_`, or `_repr_jpeg_`. Pass a matplotlib figure, pandas DataFrame, altair chart, tesserax Canvas, IPython rich object, etc. directly — no `str(...)` call, no bundling, no adapters. Strings pass through unchanged.
- `examples/tesserax_demo.py` showcasing the pattern with live SVG via [tesserax](https://github.com/apiad/tesserax). Install the optional group with `uv sync --extra examples` to run it.

## 3.3.0

### Added

- **Public relay** (`--public`) — share your presentation with anyone via an instant public URL. Your laptop runs the deck, a lightweight relay forwards WebSocket messages to viewers worldwide.
- **Custom URL names** (`--name`) — `auditorium run talk.py --public --name my-talk` gives you `http://relay/r/my-talk/` instead of a random hash. Duplicate names are rejected.
- **`auditorium relay`** — run your own relay server. Self-hostable, one command. Includes systemd service file and Makefile targets (`relay-install`, `relay-update`, `relay-uninstall`, `relay-status`, `relay-logs`).
- Default relay at `vps.apiad.net:4243`, configurable via `--relay host:port`.
- Relay features: late-join message replay, viewer acks forwarded, viewer keypresses dropped (audience is read-only).

## 3.2.0

### Added

- **Presenter drives audience** — `--presenter` mode syncs all audience tabs to the presenter's navigation. Audience keyboards are locked. Only one presenter allowed.
- **Late-join sync** — new tabs connecting mid-slide receive the full message log and see the complete slide state immediately.
- **Dual mode** — default is independent per-tab sessions; `--presenter` enables shared navigation.
- `/presenter` page returns 403 without `--presenter` flag.

### Changed

- Replaced per-tab `Session` with `Presentation` dataclass used in both modes.
- Removed `p` key shortcut — presenter mode is now explicitly opt-in via `--presenter`.
- README rewritten with feature showcase and use-case examples.

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
