# Auditorium design

This file changes only when the architecture changes. It says how the pieces fit
and why each rule exists. For the measurements and incidents behind a rule, follow
the link to its dated spec in `docs/design/`.

The labels D1 to D9 are the ones code comments cite. They come from the 4.0 spec,
`docs/design/2026-08-26-scene-engine.md`, and keep its numbering.

## The one idea

Running a deck compiles a timeline instead of performing it. Scene code calls
`play()`, `beat()` and `wait()`, which record and advance a virtual clock; nothing
sleeps and nothing is displayed while the script runs. The result is a `Timeline`:
pure data that survives a round trip through JSON. In the browser, one function,
`seek(t)`, puts the DOM into the state it holds at time `t`. Presenting, previewing,
mirroring the presenter's stage, rendering video and exporting stills all call
`seek(t)` from a different clock.

## Components and their boundaries

```
deck.py ─ scene.py ─ nodes.py      authoring: Python, runs once at compile time
   │       slide.py (shim)
   │       layout.py
   ▼
compile.py ──► timeline.py          pure data: nodes, ops, tracks, beats, markers, audio
                   │
                   ▼  /timeline.json
            static/engine.js        seek(t): the only runtime
                   │
     ┌─────────────┼──────────────┬──────────────┐
  index.html    preview.html   presenter.html   render.py / exporter.py
  (present)     (authoring)    (notes, mirror)  (Playwright drives seek per frame)
```

- **Authoring** (`deck.py`, `scene.py`, `nodes.py`, `slide.py`, `layout.py`) emits
  ops and tracks at the current virtual time. It never touches a browser.
  `@deck.slide` is a shim over `@deck.scene`: `step()` becomes `beat()` and
  `sleep()` becomes `wait()`.
- **The timeline** (`timeline.py`) is the contract between compiling and playing.
  It holds no reference to a live Python object, because JSON is how it reaches
  the browser. Ops are discrete structural changes at an instant; tracks are
  continuous property animations over an interval. All times are integer
  milliseconds.
- **The engine** (`auditorium/static/engine.js`) applies ops up to `t`, pins every animation on
  the page to `t`, runs JS tweens, then resolves anchors. `auditorium/static/client.js` holds
  what the three browser surfaces share, so a page may add chrome and nothing else.
- **The server** (`server.py`) compiles the deck, serves the shells and the
  timeline, watches the source file for hot reload, and relays presenter commands.
  It holds no playback position: the browser owns the timeline.
- **The renderer** (`render.py`) maps output frames to timeline positions with a
  pure function, seeks Chromium to each one, screenshots, and encodes with ffmpeg.
  **The exporter** (`exporter.py`) seeks to each beat and saves HTML or PNG stills.
- **The relay** (`relay.py`) is a WebSocket proxy that gives `--public` a shareable
  URL. It is independent of the engine.

## Rules and their reasons

**D1. Compile, don't perform.** `play()` records and returns. This is what makes
time addressable, rendering deterministic and arbitrary Python (loops, numpy,
recursion) usable inside an animation. The cost, accepted from manim, is that a
scene cannot branch on what a viewer does.

**D2. `seek(t)` is the only runtime primitive.** A second path that computes DOM
state can disagree with the first, and the disagreement shows up as "the render
doesn't look like the preview". When JS must reimplement a Python rule (the
preview's rendered-frame counter reimplements `render_schedule`), a test asserts
the two agree.

**D3. Every animation is paused and persistent.** Animations use `fill: both` (or
`infinite`) and move only by assignment to `currentTime`. Bare `transition:` rules
are banned in shipped CSS, because a CSS transition leaves `getAnimations()` when
it finishes and every later backward seek past it silently does nothing.

**D4. `seek` drives `document.getAnimations()`, never a private registry.** Themes
ship infinite animations on pseudo-elements, which a registry cannot see, and an
unpaused animation makes every frame differ between runs.

**D5. A backward seek resets to zero and replays forward.** Seeking is
path-dependent: the same `t` reached by rewinding differs from `t` reached fresh,
by tens of pixels of layout drift. Forward-only seeks always agree, which is also
what makes rendering frame ranges in parallel safe.

**D6. Anchors resolve in the browser, reads batched before writes.** Python never
models CSS layout, so an arrow follows its box through motion and flex reflow.
Interleaving reads and writes thrashes layout at 182 ms a frame for 2000 anchors,
against a 33 ms budget.

**D7. `@deck.slide` stays, as a shim.** The construction vocabulary carries no
timing, so two mappings keep every existing deck running.

**D8. Separate surfaces for separate jobs.** Authoring wants a scrubber, frame
stepping and loop-a-range; presenting wants none of it on screen. Both are thin
pages over the same engine, so the second one costs little.

**D9. Render scope.** mp4 by default, webm and PNG sequences on request,
addressable by frame range (`--from`/`--to`), one audio bed mixed at encode time.
Frame ranges were cheap to build first and expensive to retrofit.

Rules added after the spec:

- **Surfaces share intent, not positions.** The presenter broadcasts `seek t` or
  `playTo from→to`, and only the presenter's socket may drive. Every surface runs
  the same deterministic engine, so a command is enough, and the server enforces
  who drives rather than trusting a client's key handler.
- **The presenter mode is in the HTML shell, not the socket.** The audience decides
  whether to autoplay before its first frame, and waiting for the handshake would
  race it.
- **The stage is a fixed 1920×1080 box scaled by `transform`.** Themes size type in
  `rem`, so resizing the box would reflow text into a layout the renderer never
  produces.
- **Themes carry the palette; geometry names a role.** A node says `series=2` or
  `muted=True` and the theme picks the colour, so a figure keeps its meaning when
  the theme changes. Series are explicit, never assigned by draw order, because an
  inserted axis would renumber every colour after it. See
  `docs/design/2026-08-27-themed-math-and-geometry.md`.
- **Everything the browser loads is vendored.** KaTeX, highlight.js and fonts ship
  inside the package, so a deck runs offline and a render does not depend on a CDN.
- **No PDF export.** A timeline has no canonical instant to print, so the format
  was removed in 4.0 instead of guessed at.

## What a machine checks and what a reader judges

Tests check that compilation lands tracks and beats at the right times, that
`seek` reproduces computed styles (pseudo-element animations and anchored arrows
included), that a rewind followed by a replay matches a fresh forward pass, that
two renders are byte-identical, that the preview's frame counter matches the
renderer's schedule, that shipped CSS has no bare transitions and that every colour
theme defines the geometry palette.

No test can say whether a scene reads well. That takes looking at rendered frames,
which is why "done" for a new primitive includes watching it in the demo.

## Non-goals

- Scenes that branch on viewer input (D1).
- Geometry that negotiates space with flowing text. Overlap is an authoring
  mistake, and layout-aware SVG would be a separate design.
- Path morphing faked as a cross-fade. `Path` draws on and moves; morphing between
  paths with different command counts waits for a real normalisation step.
- PDF output.

Deferred rather than rejected, with the spec's reasoning: `--jobs N`, voiceover
synced to beats, multi-track audio, alpha output, GIF, cloud rendering.

## Specs

`docs/design/` holds the dated specs this file summarises. The 2.0 rewrite design
it replaced is `docs/design/2026-04-17-auditorium-2-rewrite.md`, kept as history:
its server-driven mutation protocol is gone.
