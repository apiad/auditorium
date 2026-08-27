---
type: design_doc
date: 2026-08-26
title: "Auditorium 4.0: the scene engine"
status: draft
tags: [auditorium, animation, video, timeline, waapi, playwright, rendering]
---

# Auditorium 4.0: the scene engine

## Overview

Auditorium 4.0 repositions the project from a live presentation framework into a
declarative HTML/CSS animation and video framework — manim for the web. The
target output is marketing clips, animated infographics, and algorithm
visualisations: short, dense, animated pieces authored in Python and rendered to
mp4. Static lecture material is no longer the centre of gravity; scriptorium
covers Markdown-to-PDF, and auditorium's presentation mode survives as one
consumer of the new engine rather than as its reason for existing.

The change is architectural and rests on a single idea. Today, slide functions
execute in real time and push DOM mutations over a WebSocket, one acknowledgment
per mutation; time is an event, not a coordinate, and there is no way to ask what
the deck looks like at a given instant. In 4.0, running a deck **compiles** a
timeline instead of performing it. `play()` and `beat()` record; nothing executes
against a wall clock. The compiled timeline is a serializable artifact, and every
consumer — presenting, previewing, rendering — is a thin wrapper around one
runtime primitive, `seek(t)`, which puts the DOM into the state it holds at time
`t`.

That collapse is the point. Interactive playback is `seek` driven by a
requestAnimationFrame clock; scrubbing is `seek` driven by a slider; rendering is
`seek` driven by a frame counter, followed by a screenshot. There is no separate
render path that can drift out of agreement with what the author saw, which is
precisely the defect in the current `record` command: it screen-captures a live
browser and produces a different video on a loaded machine.

Python remains real. Because `play()` only records, an authoring script runs to
completion at compile time, so loops, recursion, numpy, and arbitrary computation
work without ceremony. An animated bubble sort is a bubble sort that calls
`play()` in its inner loop. The cost of that model, inherited from manim, is that
the timeline is fully determined before playback: scenes cannot branch on what a
viewer does.

The existing construction vocabulary — `show`, `md`, `title`, `subtitle`,
`section`, `block`, `columns`, `rows`, `place` — is timing-agnostic and carries
forward unchanged. Only `step()` and `sleep()` are timing primitives, and both
map onto the new model, so `@deck.slide` survives as a thin compatibility shim
over the scene engine and existing decks keep working.

## Components

### The timeline

The compiled artifact and the contract between stages. Pure data, JSON-serializable,
with no reference to Python objects:

```json
{
  "version": 1,
  "meta": { "title": "...", "fps": 30, "size": [1920, 1080], "duration_ms": 12400 },
  "theme_css": "...",
  "nodes": [
    { "id": "n1", "layer": "dom", "html": "<div class=...>", "parent": "root" },
    { "id": "n2", "layer": "svg", "kind": "arrow",
      "from": { "anchor": "n1.right" }, "to": { "anchor": "n3.left" } }
  ],
  "ops":   [ { "t": 0, "action": "append", "node": "n1" },
             { "t": 2000, "action": "remove", "selector": "#n1" } ],
  "tracks":[ { "node": "n1", "prop": "opacity",
               "from": 0, "to": 1, "start": 0, "end": 500, "ease": "out-cubic" } ],
  "beats": [ 1300, 4200, 7000 ],
  "audio": [ { "src": "track.mp3", "at": 0 } ]
}
```

Two kinds of entry, and the distinction matters: **ops** are discrete structural
mutations at an instant (a node enters or leaves the DOM), while **tracks** are
continuous property animations over an interval. Ops are the reason `seek` needs
care; tracks are trivially seekable.

### The scene context

`scene.py` exposes what an authoring script calls. It holds a compile-time clock
in milliseconds and appends to the timeline:

```python
@deck.scene
async def pricing(s):
    box = await s.show(Box("$29/mo"), at=(100, 200))
    await s.play(FadeIn(box), run_time=0.5)
    await s.play(box.animate.move_to(400, 200), run_time=0.8, ease="out-cubic")
    await s.beat()
    await s.play(CountUp(box.label, 0, 1_000_000), run_time=2.0)
```

- `play(*anims, run_time, ease, lag=0)` appends one track per animation starting
  at the current clock, then advances the clock by `run_time`. Multiple
  animations in one call overlap; `lag` staggers their starts.
- `beat(hold=None)` records a pause point. Interactive mode waits there for a
  keypress regardless of `hold`; rendering dwells for `hold` seconds, defaulting
  to `Deck(beat_hold=...)` and ultimately to `0.0`, so an authored scene plays
  through its beats. The compat shim passes a non-zero default (1.5s) because a
  slide deck rendered to video with zero-length steps would blast past every
  reveal.
- `wait(seconds)` advances the clock with nothing animating.
- `node.animate.<method>(...)` is a proxy returning a track description rather
  than mutating anything.

Construction calls (`show`, `md`, `title`, …) emit an op at the current clock.
The methods stay `async` so the compat shim and the existing vocabulary need no
signature changes, even though nothing awaits I/O during compilation.

### The scene graph

`nodes.py` holds two node families sharing one coordinate space.

**DOM nodes** — `Text`, `Box`, `Card`, `Markdown`, `Image` — are HTML, styled by
the existing theme system, laid out by the existing flex primitives. Animatable
properties are transform, opacity, colour, size, and filter.

**SVG nodes** — `Line`, `Arrow`, `Path`, `Circle` — live in a full-viewport SVG
overlay and add what CSS cannot express: stroke draw-on, path interpolation,
geometric motion.

An SVG node may take a **symbolic anchor** on a DOM node (`Arrow(from=box_a.right,
to=box_b.left)`). Python never computes layout; anchors resolve in the browser at
seek time, so an arrow tracks its box through any motion, including flex reflow.

### The runtime: `seek(t)`

`static/engine.js`. The whole runtime, and small enough to state completely:

1. Apply every op with `t' <= t` that is not yet applied.
2. For every animation in `document.getAnimations()`: `pause()`, then set
   `currentTime = t`.
3. Run every registered JS tween callback with `t`.
4. Resolve anchors: batch **all** `getBoundingClientRect()` reads, then batch
   **all** SVG geometry writes.

Step 2 is why tracks are positioned with `delay` on the global timeline origin
rather than relative to their own start: with `fill: both` and a global origin,
one assignment of `currentTime = t` puts every animation at the correct point,
whether it has not yet begun, is mid-flight, or finished long ago.

The JS tween registry in step 3 covers what WAAPI cannot interpolate — counting
numbers, path morphs, text effects. It supplements `getAnimations()`; it never
replaces it.

### The server

`server.py` sheds the per-mutation acknowledgment protocol entirely. Its job
becomes: compile the deck, serve the timeline and the shell, watch the source
file, and push a recompiled timeline on change. Playback is local to the browser,
so latency stops being a factor in perceived motion.

### The clients

Two thin surfaces over the same timeline.

- `present` — today's UX. Fullscreen, no chrome, space plays to the next beat,
  presenter view on `p`. Backward navigation now works.
- `preview` — the authoring surface. Scrubber, time readout, frame counter,
  loop-a-range, single-frame stepping, and hot reload that holds position at the
  current `t` rather than restarting.

### The renderer

`render.py` replaces `recorder.py`. It launches Playwright, waits for the frame-0
readiness gate, then for each frame calls `seek(n/fps)` and screenshots, piping
frames to ffmpeg. It accepts `--from`/`--to`; a worker whose range starts at
`t > 0` forward-replays from zero without screenshotting, preserving determinism.

`exporter.py` (PDF, PNG, self-contained HTML) keeps working by seeking to each
beat instead of driving the deck live.

### The compatibility shim

`slide.py` becomes a restricted `SceneContext`. `step()` maps to `beat()`;
`sleep(x)` maps to `wait(x)`. The `instant_sleep` branch (`slide.py:261-272`) and
the `auto_step` branch in `step()` (`slide.py:240-252`) are deleted: both exist
only to fake a timeline for the exporter, and the timeline is now real.

## Decisions

### D1. Compile, don't perform

`play()` records a track and returns; it never sleeps. The authoring script runs
to completion before anything is displayed.

**Rationale.** This is the single change that makes everything else possible —
addressable time, deterministic rendering, seeking, parallelism. It also
preserves arbitrary Python integration, auditorium's original thesis, because
computation happens at compile time where it is unconstrained. The cost is that
scenes cannot branch on viewer input; manim accepts the same trade and the use
cases here do not need branching.

### D2. `seek(t)` is the only runtime primitive

Present, preview, and render are wrappers around it.

**Rationale.** Any second path that computes DOM state can disagree with the
first, and the disagreement will surface as "the render doesn't look like the
preview" — the exact failure the current architecture has. One primitive makes
that class of bug unrepresentable.

### D3. Every animation must be paused and persistent

Animations are declared with `fill: both` (or `infinite`) and driven only by
assignment to `currentTime`. Bare `transition:` rules are banned in themes;
`static/theme.css:146` becomes a keyframe animation.

**Rationale.** Determinism comes from `pause()`, not from any particular API — a
paused CSS `@keyframes` animation is pixel-deterministic across forward, reverse,
and repeat passes, and an unpaused one is nondeterministic at every interior
point. The disqualifying property of a CSSTransition is **lifetime**: it is
removed from `document.getAnimations()` the instant it finishes, after which every
backward seek past it silently no-ops and the element strands at its end value.
`fill: both` keyframes seek backward exactly.

This supersedes an earlier draft that claimed CSS transitions cannot be seeked
and proposed migrating the fourteen `--aud-transition` declarations to WAAPI.
Those are `animation-name` with `@keyframes` — CSSAnimation, already seekable —
so no migration is needed.

### D4. `seek` drives `document.getAnimations()`, never a private registry

**Rationale.** A private registry structurally cannot see animations on
pseudo-elements, and three ship in the current themes — `themes/terminal.css:49`,
`themes/neon.css:63`, and `static/theme.css:177`, all `infinite`, all wall-clock,
all on screen in every deck using those themes. Measured against the real
stylesheet, registry-only seek left five of seven frames unreproducible; freezing
`document.getAnimations()` was deterministic; freezing while skipping
pseudo-elements returned to five of seven broken.

### D5. Backward seek resets and replays forward

`seek(t)` where `t` is earlier than the current position resets to zero and
forward-seeks. Seeking is never performed backward.

**Rationale.** Seeking is empirically path-dependent: t=0 reached fresh differs
from t=0 reached by rewinding from t=1500, by 36 pixels of bounding-box drift.
Each path is individually stable, so this is hysteresis in layout and op
application, not noise. Forward-only sequences agree with each other, which is
why parallel segment rendering is safe — but preview scrubbing and present-mode
rewind would otherwise display states the renderer never produces, breaking D2's
guarantee at exactly the moment an author relies on it.

Resetting restores the guarantee rather than weakening it, and it is affordable:
5000 paused animations seek in 2.35 ms, so the only real cost is DOM
reconstruction. If scrubbing measures slow on real scenes, the escape hatch is
snapshotting DOM state at each beat and resetting to the nearest preceding beat
instead of to zero. Not built in v1.

### D6. Anchors resolve in the browser, in separated read and write phases

**Rationale.** Resolving in the browser keeps CSS layout modelling out of Python.
Phase separation is a correctness-adjacent performance requirement, not an
optimisation: naive read/write interleaving costs 182 ms per frame at 2000
anchors — 5.5× over a 33 ms budget — and 965 ms at 5000, because it thrashes
layout. Batching all reads before all writes gives 9.9 ms and 21 ms respectively,
a 45.9× improvement that brings both inside a frame. The pathological case is
precisely the dense node-and-edge graph this framework exists to draw.

### D7. `@deck.slide` becomes a shim, not a casualty

**Rationale.** The construction vocabulary is timing-agnostic, so the shim is two
mappings. Existing decks, the seven showcase decks, and the published Pages
examples keep working, and `demo_deck.py` stays living documentation instead of
becoming a rewrite chore. Version moves to `1!4.0.0` because `sleep()` changes
from "block for N seconds" to "play N seconds of timeline" — near-identical in
practice, not identical enough to call minor.

### D8. Two clients, not one surface with toggleable chrome

**Rationale.** Tuning an ease curve and delivering a lecture are different jobs.
Authoring wants loop-a-range and frame stepping; presenting wants that UI gone
without having to remember to hide it. Both are thin wrappers over an identical
timeline, so the marginal cost of the second is small.

### D9. v1 render scope

mp4 (h264, `yuv420p`) by default, with `png-sequence` and webm available.
`--size` defaults to 1920×1080 with named `vertical` (1080×1920) and `square`
presets. `--fps 30` by default. Sequential rendering, but frame-range addressable
via `--from`/`--to`. A single audio bed mixed at the ffmpeg step
(`deck.audio(path, at=)`).

Deferred: `--jobs N`, beat-synced voiceover, multi-track audio, alpha output,
GIF, cloud rendering, the editor toolkit.

**Rationale.** Frame-range addressability is cheap now and expensive to retrofit,
and it was verified to buy real parallelism — segments rendered in separate
Chromium processes came out byte-identical to a sequential render across nine
comparisons. So `--jobs` becomes a shell-level fan-out plus `ffmpeg concat` on day
one, and a proper flag is a small later addition.

## Failure modes

**Unpaused decorative animations.** Any theme animation not driven through
`seek` reintroduces wall-clock nondeterminism, and it does so silently — the
render simply differs run to run. Mitigation: D4 plus a lint that rejects bare
`transition:` in shipped themes.

**Fonts and images not ready at frame 0.** Produces a blank or unstyled first
frame with no error. Measured: without a gate, exactly one bad frame at t=0.
Mitigation: gate on `document.fonts.ready` plus explicit image decode before
frame 0. Throwaway warm-up frames were tested and do nothing.

**Throughput has no headroom.** Screenshots measure 70.8 ms median and 80.7 ms
p95 at 1920×1080, so 900 frames take 64 seconds and a 60-second clip takes about
two minutes. Acceptable for v1, but it means `--jobs` is wanted sooner than its
deferral suggests.

**Path-dependence regressing.** D5 is easy to violate by adding an "optimised"
backward seek. Mitigation: the path-independence test below is the guard, and it
fails against the current themes today.

**Playwright cannot install Chromium on Ubuntu 26.04.** Blocks the entire render
path on zion: `playwright install chromium` refuses the platform, and only a
cached `chromium-1228` works, via `executable_path`. This is a precondition, not
a design question, and it is task zero of the plan.

## Testing

**Compile** is pure Python and needs no browser: assert that tracks land at the
right times, that beats fall where expected, that overlapping `play()` calls
produce overlapping intervals, and that a timeline round-trips through JSON.

**`seek(t)`** gets browser tests asserting computed style at chosen times,
including at least one pseudo-element animation and one anchored SVG arrow.

**Path independence** replaces the golden-frame test proposed in the first draft.
Capture frames forward across a fixture; seek to the end; re-capture the same
frames; assert equality. The earlier "render twice and compare" cannot catch the
D5 defect because both runs travel forward.

**Determinism across processes** is worth keeping as a cheap regression: render a
range in one process and in two halves in separate processes, assert the
concatenation is byte-identical.

## Open questions

**SVG path morphing** is untested. Interpolating between paths with differing
command counts needs normalisation, and whether that lands in v1 or degrades to a
cross-fade is undecided until it is tried.

**Hot-reload holding position** is untested. Recompiling a timeline whose node
identities have shifted may not have a meaningful "same `t`" to hold.

**Audio when the timeline is shorter than the track.** Truncate, fade out, or
error. Defaulting to fade-out, revisited on first real use.

## Delivery order

The work stages naturally, and each stage leaves the repo in a shippable state:

1. **Engine.** Timeline, compile stage, `seek(t)`, and the `present` client.
   Ends with the shim in place and every existing deck running on the new
   runtime. This is the stage that can break things, so it goes first and alone.
2. **Preview client.** Scrubber, frame stepping, loop-a-range, hot reload.
3. **Renderer.** Frame-stepped capture, ffmpeg, `--from`/`--to`, audio bed.
   Depends on the playwright fix landing first.
4. **SVG layer.** Geometric nodes, anchors, draw-on.

Stages 2 and 3 are independent of each other. Stage 4 is where the untested
risks concentrate, which is why it comes last rather than being interleaved.

## Glossary

**Timeline.** The compiled artifact: nodes, ops, tracks, beats, audio.

**Op.** A discrete structural mutation at an instant.

**Track.** A continuous property animation over an interval.

**Beat.** A pause point. Interactive mode waits there; rendering plays through.

**Seek.** Placing the DOM in the state it holds at time `t`. The only runtime
primitive.

**Anchor.** A symbolic reference from an SVG node to a point on a DOM node,
resolved in the browser at seek time.
