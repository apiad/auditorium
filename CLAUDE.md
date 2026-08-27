# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Auditorium 4.0 is a declarative HTML/CSS animation and video framework — manim for the web. Running a deck **compiles** a timeline rather than performing it: `play()` and `beat()` record, nothing executes against a wall clock. The compiled timeline is serializable data, and every consumer — present, preview, presenter, render — is a thin wrapper around one runtime primitive, `seek(t)`, which puts the DOM into the state it holds at time `t`.

Presentation mode survives as one consumer of that engine rather than as the reason it exists. Scenes are `async def` functions decorated with `@deck.scene`; `@deck.slide` is a compatibility shim over the same machinery.

## Commands

```bash
uv sync                                    # install dependencies
uv run auditorium run examples/demo.py     # run the demo
uv run auditorium preview examples/demo.py # authoring preview: scrub, step, loop
uv run auditorium run deck.py --no-open    # run without auto-opening browser
uv run auditorium render deck.py -o out.mp4  # render to video, frame by frame
uv run pytest                              # run tests (141 passing)
uv run ruff check auditorium/              # lint
```

## Architecture

Playback is local to the browser. The server compiles the deck and serves the timeline; each client holds it and seeks itself, so latency is not a factor in perceived motion and there is no per-mutation chatter.

**Request flow:** client fetches `/timeline.json`, loads it into `AuditoriumEngine`, and drives `seek(t)` from a rAF clock (present/preview) or a frame counter (render). The WebSocket carries only three things: a `hello`/`hello_ack` handshake, a `reload` push when the source file changes, and — in `--presenter` mode — `cmd` messages relaying the presenter's *intent* (`seek t`, `playTo from→to`) to audience sockets.

**Two invariants worth knowing before touching the engine.** `seek` drives `document.getAnimations()`, never a private registry, because themes ship infinite animations on pseudo-elements a registry cannot see. And seeking is path-dependent, so it is only ever performed forward: a backward seek resets to zero and replays.

**Key modules:**

- `server.py` — FastAPI app. Compiles the deck, serves the three shells and `/timeline.json`, watches the source, and relays presenter commands. A `Presentation` holds sockets, not playback state: the browser owns the timeline and seeks locally, so the server has no position to keep (`last_cmd` is a cached message for late joiners, not computed state). The per-mutation ack protocol is gone — `tests/test_server.py` asserts `pending_acks` and `send_mutation` do not reappear.
- `deck.py` — `Deck` class with `@slide` decorator. Slides ordered by registration order, overridable with `order=N`. No `run()` method; the CLI owns the server lifecycle.
- `slide.py` — `ConstructionVocabulary` plus `SlideContext`, the 4.0 compatibility shim wrapping a `SceneContext` (`step()` maps to `beat()`, `sleep(x)` to `wait(x)`). Exposes the async vocabulary (`show`, `hide`, `replace`, `set_class`, `remove_class`, `md`, `show_md`, `step`, `sleep`) and layout methods (`columns`, `rows`, `place`). Maintains `_target_stack` for layout region scoping. Layout sizing accepts ints (proportional) or `"auto"` (natural size) — e.g. `rows(["auto", 1, "auto"])` for header/body/footer.
- `nodes.py` — The geometric vocabulary: `Line`, `Arrow`, `Circle`, `Path`, and `Anchor`. An anchor is a *symbolic* reference to a side of a DOM node, never a coordinate — Python computes no layout (D6), and the browser resolves it on every seek so an arrow tracks its box through motion and reflow. Stroke `dash` values are normalized (fractions of the shape's length) because every node carries `pathLength="1"` for draw-on.
- `scene.py` — `SceneContext`, `AnimateProxy` (`fade_in/out`, `move_by`, `rotate_by`, `scale_to`, `draw_on`) and `NodeHandle` with its five anchors. `show(into=)` composes DOM nodes without wrapping; the region path wraps, this one must not, or composition parents into the wrapper.
- `layout.py` — `Region` (async context manager for `with` block scoping), layout factory functions. Top-level layouts auto-remove `justify-center` from `#slide-root` to switch from centered to fill mode.
- `cli.py` — Typer CLI. `run`, `preview`, `render`, `export`, `relay`. `run` and `preview` share `_serve()` and differ only in which surface they open and whether shared navigation is on. SIGINT is set to SIG_DFL for clean shutdown.
- `render.py` — Frame-stepped video rendering, the fourth consumer of `seek(t)`. `render_schedule()` is a pure function mapping each output frame to a timeline position (inserting beat dwells), so the frame plan is testable without a browser. `render_frames()` captures PNGs through `window.__auditoriumShow` — never `AuditoriumEngine.seek` directly, because the client autoplays on load and would race the capture. `render_video()` encodes via ffmpeg. Takes `--from`/`--to`, so parallel rendering is a shell-level fan-out. Replaced `recorder.py`, which screen-captured a live browser and was nondeterministic.
- `exporter.py` — Static export to self-contained HTML or PNG stills. **No PDF**: a timeline has no canonical instant to print, so the format was removed in 4.0 rather than guessed at. See Readme.md. Drives by seeking to each beat (Playwright + ephemeral uvicorn). For HTML: inlines all assets into a single file. For PNG: one still per beat. Optional dep: `auditorium[record]`.
- `static/index.html` — The audience shell. All assets are local (KaTeX, highlight.js, fonts vendored under `static/vendor` and `static/fonts`) — no outbound requests, so a deck runs offline. Its inline module is thin: chrome updates, the keydown map, and the presenter-mode branch. Everything else comes from `client.js`.
- `static/engine.js` — The whole runtime: `seek(t)` applies ops forward, pins every animation on the page to timeline time, runs JS tweens, then resolves anchors in one batched read phase followed by one batched write phase (interleaving costs 182ms/frame at 2000 anchors against a 33ms budget). SVG nodes are built with `createElementNS` — `innerHTML` on an HTML parent yields HTMLUnknownElements that never render. Screen rects convert to overlay user units via `getScreenCTM`, which is what makes anchors correct inside the scaled preview and presenter stages. Both `reset()` and the `clear` op empty the overlay but keep `<defs>`, or the arrowhead marker dies on the first rewind.
- `static/svg-layer.css` — Overlay positioning. Its own file, not part of theme.css: it is engine contract, not appearance. No `viewBox`, deliberately — that would add a second silent coordinate mapping on top of the CTM conversion.
- `static/client.js` — What every client surface shares: timeline fetch, the KaTeX/highlight.js append hook, beat arithmetic, marker lookup, and a rAF clock driving `seek`. Three pages consume it (`index`, `preview`, `presenter`); a second implementation of "what does the deck look like at t" is exactly the drift D2 forbids. Also owns `renderFrameOf`/`renderFrameCount`, which reimplement `render_schedule`'s beat-dwell rule in JS — `tests/test_preview_frames.py` asserts the two agree, because two implementations of one rule drift silently.
- `static/preview.html` + `preview.css` — The authoring client at `/preview` (`auditorium preview`). Scrubber with beat ticks, frame stepping, loop-a-range, position-holding hot reload. The stage is a fixed 1920×1080 box scaled by `transform`, never resized: themes size type in `rem`, so a resized box reflows text into a layout the renderer never produces. The transform also gives the `position: fixed` chrome its containing block.
- `static/presenter.html` + `presenter.css` — Presenter view at `/presenter`, rebuilt in 4.0 over the timeline. Stage mirror, speaker notes and next-scene preview from `timeline.markers`, elapsed timer. The mirror is its own engine seeking the same timeline, not a DOM copy. Drives the audience by broadcasting intent (`{type:"cmd", cmd:"seek"|"playTo"}`) which the server relays to audience sockets only; the audience does not autoplay in this mode, and learns the mode from a `<meta>` the server injects into the shell (over the socket it would race the first frame).

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

`examples/demo.py` is the living documentation, and it is a set of **scenes that move** — not a vocabulary tour. It replaced `demo_deck.py`, which was 25 shim slides of `step()` reveals against 4 scenes: on screen that was a slideshow that faded, which is the opposite of what 4.0 is for.

When adding an animation primitive, add it to `demo.py` and **watch the render** — `tests/test_examples.py` asserts the demo still exercises motion, but only looking at frames tells you it reads. Two gotchas the demo documents in comments because they cost real time to find: `show()` wraps content in a div and the handle refers to that **wrapper**, so anything you anchor to must fill it; and a top-level `rows()`/`columns()` drops the root out of centred mode, so scenes give their content an explicit stage height.

The deck is authored for 1920x1080 — translations are CSS pixels, so `PITCH` and the stage offsets assume that size.
