# Auditorium 4.0 Scene Engine — Stage 1 (Engine) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace auditorium's real-time WebSocket runtime with a compiled timeline driven by a single `seek(t)` primitive, leaving every existing deck working through a compatibility shim.

**Architecture:** Running a deck compiles a serializable `Timeline` (nodes, ops, tracks, beats) instead of performing it — `play()` records, nothing sleeps. The browser receives the whole timeline and plays it locally; `seek(t)` puts the DOM into the state it holds at time `t` by applying ops forward, assigning `currentTime = t` to every animation in `document.getAnimations()`, and running JS tween callbacks. Backward seeks reset to zero and replay forward, because seeking is path-dependent. `@deck.slide` becomes a restricted `SceneContext` so existing decks keep running.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, pytest, pytest-asyncio, Playwright (Chromium), Web Animations API, vanilla JS (no build step).

**Spec:** `docs/design/2026-08-26-scene-engine.md`

## Global Constraints

- Version stays on the PEP 440 epoch. Stage 1 lands `1!4.0.0a1` in `pyproject.toml` and `cli.py`; `1!4.0.0` is tagged only when Stage 3 restores `record` and `export`. Keep the `1!` prefix — old PyPI releases used calver and the epoch is what makes semver sort above them.
- No build step. No bundler. Client JS is vanilla ES modules served from `auditorium/static/`.
- Required runtime deps stay `fastapi`, `uvicorn[standard]`, `typer`, `markdown`, `rich`. Playwright stays in the `[record]` extra.
- Every animation must be **paused and persistent** (`fill: both`, or `infinite`). Bare `transition:` rules are banned in shipped themes.
- `seek()` must drive `document.getAnimations()`. A private animation registry is never the source of truth.
- Anchor resolution batches **all** DOM reads before **all** DOM writes. Never interleave.
- All times in the timeline are integer **milliseconds**. Python-facing APIs take seconds (floats) and convert at the boundary.
- English for code, comments, identifiers, commit messages, and test names.

---

### Task 0: Unblock the browser toolchain and establish test infrastructure

Nothing in this plan is testable until Chromium launches and pytest can run async tests. This task's deliverable is a green smoke test that opens a real browser.

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `tests/test_toolchain.py`

**Interfaces:**
- Consumes: nothing.
- Produces: pytest fixture `browser_page` yielding a Playwright `Page`; module constant `auditorium.testing.CHROMIUM_PATH: str | None`.

- [ ] **Step 1: Reproduce the failure and record it**

Run: `uv run playwright install chromium`
Expected: refuses with "Playwright does not support chromium on ubuntu26.04-x64". Note the exact message; it decides which branch of Step 2 you take.

- [ ] **Step 2: Try the version bump first**

```bash
uv add --dev 'playwright>=1.62'
uv run playwright install chromium
```

If this succeeds, `CHROMIUM_PATH` stays `None` and Playwright resolves its own browser. If it still refuses the platform, continue to Step 3 for the fallback. Do not skip the bump — the fallback pins this repo to one machine's cache.

- [ ] **Step 3: Add the resolver with the cached-binary fallback**

Create `auditorium/testing.py`:

```python
"""Test-support helpers. Not imported by the runtime."""
from __future__ import annotations

import os
from pathlib import Path

_CACHED = Path.home() / ".cache/ms-playwright/chromium-1228/chrome-linux64/chrome"


def chromium_path() -> str | None:
    """Return an explicit Chromium executable path, or None to let Playwright choose.

    Playwright refuses to install Chromium on Ubuntu 26.04. When its own
    download is unavailable, fall back to a cached build. Override with
    AUDITORIUM_CHROMIUM.
    """
    override = os.environ.get("AUDITORIUM_CHROMIUM")
    if override:
        return override
    if _CACHED.exists():
        return str(_CACHED)
    return None
```

- [ ] **Step 4: Add pytest configuration and the async plugin**

```bash
uv add --dev pytest-asyncio
```

Append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 5: Write the browser fixture**

Create `tests/conftest.py`:

```python
import pytest
import pytest_asyncio

from auditorium.testing import chromium_path


@pytest_asyncio.fixture
async def browser_page():
    playwright = pytest.importorskip("playwright.async_api")
    async with playwright.async_playwright() as p:
        kwargs = {}
        path = chromium_path()
        if path:
            kwargs["executable_path"] = path
        browser = await p.chromium.launch(**kwargs)
        context = await browser.new_context(viewport={"width": 800, "height": 600})
        page = await context.new_page()
        yield page
        await context.close()
        await browser.close()
```

- [ ] **Step 6: Write the smoke test**

Create `tests/test_toolchain.py`:

```python
async def test_chromium_launches_and_evaluates(browser_page):
    await browser_page.set_content("<div id='x'>hello</div>")
    text = await browser_page.evaluate("() => document.getElementById('x').textContent")
    assert text == "hello"


async def test_web_animations_api_available(browser_page):
    await browser_page.set_content("<div id='x'></div>")
    ok = await browser_page.evaluate(
        "() => typeof document.getAnimations === 'function'"
    )
    assert ok is True
```

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_toolchain.py -v`
Expected: 2 passed. If Chromium still fails to launch, stop and report — every later task depends on this.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock auditorium/testing.py tests/conftest.py tests/test_toolchain.py
git commit -m "test: establish pytest + playwright toolchain

Playwright cannot install Chromium on Ubuntu 26.04; falls back to a
cached build via executable_path, overridable with AUDITORIUM_CHROMIUM."
```

---

### Task 1: Timeline data model

**Files:**
- Create: `auditorium/timeline.py`
- Create: `tests/test_timeline.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Node(id: str, layer: str, html: str | None, parent: str)`, `Op(t: int, action: str, node: str | None, selector: str | None, html: str | None, cls: str | None)`, `Track(node: str, prop: str, from_: float, to: float, start: int, end: int, ease: str)`, `Timeline(meta: dict, nodes: list[Node], ops: list[Op], tracks: list[Track], beats: list[Beat], audio: list[dict])` with `Timeline.to_dict() -> dict`, `Timeline.from_dict(d: dict) -> Timeline`, `Timeline.duration_ms -> int`. `Beat(t: int, hold_ms: int)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_timeline.py`:

```python
from auditorium.timeline import Beat, Node, Op, Timeline, Track


def test_empty_timeline_has_zero_duration():
    assert Timeline().duration_ms == 0


def test_duration_is_the_latest_of_ops_tracks_and_beats():
    tl = Timeline()
    tl.ops.append(Op(t=100, action="append", node="n1"))
    tl.tracks.append(Track(node="n1", prop="opacity", from_=0, to=1, start=0, end=500))
    tl.beats.append(Beat(t=900, hold_ms=0))
    assert tl.duration_ms == 900


def test_round_trips_through_dict():
    tl = Timeline(meta={"title": "T", "fps": 30, "size": [1920, 1080]})
    tl.nodes.append(Node(id="n1", layer="dom", html="<p>hi</p>", parent="root"))
    tl.ops.append(Op(t=0, action="append", node="n1"))
    tl.tracks.append(
        Track(node="n1", prop="opacity", from_=0, to=1, start=0, end=500, ease="ease-out")
    )
    tl.beats.append(Beat(t=500, hold_ms=1500))

    restored = Timeline.from_dict(tl.to_dict())

    assert restored.meta["title"] == "T"
    assert restored.nodes[0].html == "<p>hi</p>"
    assert restored.tracks[0].from_ == 0
    assert restored.beats[0].hold_ms == 1500
    assert restored.to_dict() == tl.to_dict()


def test_track_serializes_from_as_json_key_from():
    tl = Timeline()
    tl.tracks.append(Track(node="n1", prop="opacity", from_=0.0, to=1.0, start=0, end=1))
    d = tl.to_dict()
    assert "from" in d["tracks"][0]
    assert "from_" not in d["tracks"][0]


def test_is_json_serializable():
    import json
    tl = Timeline(meta={"title": "T"})
    tl.ops.append(Op(t=0, action="append", node="n1"))
    assert json.loads(json.dumps(tl.to_dict()))["ops"][0]["t"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_timeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'auditorium.timeline'`

- [ ] **Step 3: Write the implementation**

Create `auditorium/timeline.py`:

```python
"""The compiled artifact: the contract between compiling and playing.

Pure data. No reference to Deck, SceneContext, or any live object — a
Timeline must survive a round trip through JSON unchanged, because that is
how it reaches the browser.

All times are integer milliseconds.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    """An element in the scene graph."""
    id: str
    layer: str = "dom"          # "dom" | "svg"
    html: str | None = None
    parent: str = "root"

    def to_dict(self) -> dict:
        return {"id": self.id, "layer": self.layer, "html": self.html, "parent": self.parent}

    @classmethod
    def from_dict(cls, d: dict) -> Node:
        return cls(id=d["id"], layer=d.get("layer", "dom"),
                   html=d.get("html"), parent=d.get("parent", "root"))


@dataclass
class Op:
    """A discrete structural mutation at an instant."""
    t: int
    action: str                 # "append" | "remove" | "replace" | "set_class" | "remove_class"
    node: str | None = None
    selector: str | None = None
    html: str | None = None
    cls: str | None = None

    def to_dict(self) -> dict:
        return {"t": self.t, "action": self.action, "node": self.node,
                "selector": self.selector, "html": self.html, "cls": self.cls}

    @classmethod
    def from_dict(cls, d: dict) -> Op:
        return cls(t=d["t"], action=d["action"], node=d.get("node"),
                   selector=d.get("selector"), html=d.get("html"), cls=d.get("cls"))


@dataclass
class Track:
    """A continuous property animation over an interval.

    ``start`` and ``end`` are absolute positions on the global timeline, not
    offsets from the node's own creation. The browser relies on that: every
    animation is declared with ``delay = start`` against a shared origin so
    one assignment of ``currentTime = t`` positions all of them correctly.
    """
    node: str
    prop: str
    from_: float
    to: float
    start: int
    end: int
    ease: str = "linear"

    def to_dict(self) -> dict:
        return {"node": self.node, "prop": self.prop, "from": self.from_,
                "to": self.to, "start": self.start, "end": self.end, "ease": self.ease}

    @classmethod
    def from_dict(cls, d: dict) -> Track:
        return cls(node=d["node"], prop=d["prop"], from_=d["from"], to=d["to"],
                   start=d["start"], end=d["end"], ease=d.get("ease", "linear"))


@dataclass
class Beat:
    """A pause point. Interactive mode waits here; rendering dwells ``hold_ms``."""
    t: int
    hold_ms: int = 0

    def to_dict(self) -> dict:
        return {"t": self.t, "hold_ms": self.hold_ms}

    @classmethod
    def from_dict(cls, d: dict) -> Beat:
        return cls(t=d["t"], hold_ms=d.get("hold_ms", 0))


@dataclass
class Timeline:
    meta: dict = field(default_factory=dict)
    nodes: list[Node] = field(default_factory=list)
    ops: list[Op] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    beats: list[Beat] = field(default_factory=list)
    audio: list[dict] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        candidates = [0]
        candidates += [o.t for o in self.ops]
        candidates += [t.end for t in self.tracks]
        candidates += [b.t + b.hold_ms for b in self.beats]
        return max(candidates)

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "meta": {**self.meta, "duration_ms": self.duration_ms},
            "nodes": [n.to_dict() for n in self.nodes],
            "ops": [o.to_dict() for o in self.ops],
            "tracks": [t.to_dict() for t in self.tracks],
            "beats": [b.to_dict() for b in self.beats],
            "audio": list(self.audio),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Timeline:
        meta = dict(d.get("meta", {}))
        meta.pop("duration_ms", None)
        return cls(
            meta=meta,
            nodes=[Node.from_dict(x) for x in d.get("nodes", [])],
            ops=[Op.from_dict(x) for x in d.get("ops", [])],
            tracks=[Track.from_dict(x) for x in d.get("tracks", [])],
            beats=[Beat.from_dict(x) for x in d.get("beats", [])],
            audio=list(d.get("audio", [])),
        )
```

Note: `to_dict` injects `duration_ms` into `meta` and `from_dict` strips it, so the round-trip equality assertion in the test holds while the browser still receives the duration.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_timeline.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add auditorium/timeline.py tests/test_timeline.py
git commit -m "feat(timeline): serializable timeline data model"
```

---

### Task 2: SceneContext compile clock

**Files:**
- Create: `auditorium/scene.py`
- Create: `tests/test_scene.py`

**Interfaces:**
- Consumes: `auditorium.timeline.{Timeline, Node, Op, Track, Beat}`.
- Produces: `NodeHandle(id: str)` with attribute `.animate`; `SceneContext(timeline: Timeline, beat_hold_ms: int = 0)` with `async show(content, *, element_id=None) -> NodeHandle`, `async play(*anims, run_time: float = 1.0, ease: str = "linear", lag: float = 0.0) -> None`, `async beat(hold: float | None = None) -> None`, `async wait(seconds: float) -> None`, and property `t_ms: int`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scene.py`:

```python
from auditorium.scene import SceneContext
from auditorium.timeline import Timeline


def make_scene(**kw):
    tl = Timeline()
    return SceneContext(tl, **kw), tl


async def test_show_emits_a_node_and_an_append_op_at_the_current_time():
    s, tl = make_scene()
    handle = await s.show("<p>hi</p>")
    assert len(tl.nodes) == 1
    assert tl.nodes[0].id == handle.id
    assert tl.ops[0].action == "append"
    assert tl.ops[0].t == 0


async def test_wait_advances_the_clock_without_emitting_anything():
    s, tl = make_scene()
    await s.wait(1.5)
    assert s.t_ms == 1500
    assert tl.ops == []
    assert tl.tracks == []


async def test_play_appends_a_track_and_advances_the_clock():
    s, tl = make_scene()
    h = await s.show("<p>hi</p>")
    await s.play(h.animate.fade_in(), run_time=0.5)
    assert len(tl.tracks) == 1
    track = tl.tracks[0]
    assert track.prop == "opacity"
    assert (track.start, track.end) == (0, 500)
    assert s.t_ms == 500


async def test_multiple_animations_in_one_play_overlap():
    s, tl = make_scene()
    a = await s.show("<p>a</p>")
    b = await s.show("<p>b</p>")
    await s.play(a.animate.fade_in(), b.animate.fade_in(), run_time=0.5)
    assert [(t.start, t.end) for t in tl.tracks] == [(0, 500), (0, 500)]
    assert s.t_ms == 500


async def test_lag_staggers_starts_and_the_clock_covers_the_last_one():
    s, tl = make_scene()
    a = await s.show("<p>a</p>")
    b = await s.show("<p>b</p>")
    await s.play(a.animate.fade_in(), b.animate.fade_in(), run_time=0.5, lag=0.2)
    assert [(t.start, t.end) for t in tl.tracks] == [(0, 500), (200, 700)]
    assert s.t_ms == 700


async def test_beat_records_a_pause_and_advances_one_millisecond():
    """The 1ms keeps post-beat content from being visible at the beat itself."""
    s, tl = make_scene()
    await s.wait(1.0)
    await s.beat()
    assert tl.beats[0].t == 1000
    assert tl.beats[0].hold_ms == 0
    assert s.t_ms == 1001


async def test_content_after_a_beat_is_not_visible_at_the_beat():
    s, tl = make_scene()
    await s.show("<p>before</p>")
    await s.beat()
    await s.show("<p>after</p>")
    beat_t = tl.beats[0].t
    visible_at_beat = [o for o in tl.ops if o.t <= beat_t]
    assert len(visible_at_beat) == 1


async def test_beat_hold_defaults_come_from_the_scene():
    s, tl = make_scene(beat_hold_ms=1500)
    await s.beat()
    assert tl.beats[0].hold_ms == 1500


async def test_explicit_beat_hold_overrides_the_scene_default():
    s, tl = make_scene(beat_hold_ms=1500)
    await s.beat(hold=0.25)
    assert tl.beats[0].hold_ms == 250


async def test_ease_names_map_to_css_easing_functions():
    s, tl = make_scene()
    h = await s.show("<p>hi</p>")
    await s.play(h.animate.fade_in(), run_time=0.5, ease="out-cubic")
    assert tl.tracks[0].ease == "cubic-bezier(0.33, 1, 0.68, 1)"


async def test_move_to_emits_two_tracks_one_per_axis():
    s, tl = make_scene()
    h = await s.show("<p>hi</p>")
    await s.play(h.animate.move_to(400, 200), run_time=0.8)
    props = sorted(t.prop for t in tl.tracks)
    assert props == ["transform.x", "transform.y"]


async def test_nothing_sleeps_during_compilation():
    import time
    s, _ = make_scene()
    h = await s.show("<p>hi</p>")
    started = time.monotonic()
    await s.play(h.animate.fade_in(), run_time=5.0)
    await s.wait(10.0)
    assert time.monotonic() - started < 0.5
    assert s.t_ms == 15000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scene.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'auditorium.scene'`

- [ ] **Step 3: Write the implementation**

Create `auditorium/scene.py`:

```python
"""Compile-time scene construction.

Nothing here executes in real time. ``play()`` records tracks and advances a
virtual clock; the authoring script runs to completion before anything is
displayed. That is what makes arbitrary Python — loops, recursion, numpy —
usable for animation, and what makes the result seekable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auditorium.timeline import Beat, Node, Op, Timeline, Track

EASINGS = {
    "linear": "linear",
    "ease": "ease",
    "in": "ease-in",
    "out": "ease-out",
    "in-out": "ease-in-out",
    "out-cubic": "cubic-bezier(0.33, 1, 0.68, 1)",
    "in-cubic": "cubic-bezier(0.32, 0, 0.67, 0)",
    "out-back": "cubic-bezier(0.34, 1.56, 0.64, 1)",
}


def resolve_ease(name: str) -> str:
    """Map a friendly easing name to a CSS easing function.

    Unknown values pass through so callers can supply raw cubic-bezier().
    """
    return EASINGS.get(name, name)


@dataclass
class AnimSpec:
    """A description of one property animation. Produced by the .animate proxy."""
    node: str
    prop: str
    from_: float | None
    to: float


class AnimateProxy:
    """Turns ``handle.animate.move_to(x, y)`` into AnimSpec objects.

    Returns descriptions; mutates nothing. ``play()`` decides when they run.
    """

    def __init__(self, node_id: str) -> None:
        self._node = node_id

    def fade_in(self) -> list[AnimSpec]:
        return [AnimSpec(self._node, "opacity", 0.0, 1.0)]

    def fade_out(self) -> list[AnimSpec]:
        return [AnimSpec(self._node, "opacity", 1.0, 0.0)]

    def move_to(self, x: float, y: float) -> list[AnimSpec]:
        return [
            AnimSpec(self._node, "transform.x", None, x),
            AnimSpec(self._node, "transform.y", None, y),
        ]

    def scale_to(self, factor: float) -> list[AnimSpec]:
        return [AnimSpec(self._node, "transform.scale", None, factor)]


@dataclass
class NodeHandle:
    """Author-facing reference to a scene node."""
    id: str

    @property
    def animate(self) -> AnimateProxy:
        return AnimateProxy(self.id)


class SceneContext:
    def __init__(self, timeline: Timeline, *, beat_hold_ms: int = 0) -> None:
        self._tl = timeline
        self._t = 0
        self._counter = 0
        self._beat_hold_ms = beat_hold_ms

    @property
    def t_ms(self) -> int:
        return self._t

    def _next_id(self) -> str:
        self._counter += 1
        return f"n{self._counter}"

    async def show(self, content: Any, *, element_id: str | None = None) -> NodeHandle:
        from auditorium.slide import _jupyter_to_html

        node_id = element_id or self._next_id()
        self._tl.nodes.append(
            Node(id=node_id, layer="dom", html=f"<div>{_jupyter_to_html(content)}</div>")
        )
        self._tl.ops.append(Op(t=self._t, action="append", node=node_id))
        return NodeHandle(id=node_id)

    async def play(
        self,
        *anims: list[AnimSpec],
        run_time: float = 1.0,
        ease: str = "linear",
        lag: float = 0.0,
    ) -> None:
        """Record one or more animations starting now. Advances the clock."""
        css_ease = resolve_ease(ease)
        duration = int(run_time * 1000)
        end = self._t
        for i, spec_list in enumerate(anims):
            start = self._t + int(lag * 1000 * i)
            for spec in spec_list:
                self._tl.tracks.append(
                    Track(
                        node=spec.node,
                        prop=spec.prop,
                        from_=spec.from_ if spec.from_ is not None else 0.0,
                        to=spec.to,
                        start=start,
                        end=start + duration,
                        ease=css_ease,
                    )
                )
            end = max(end, start + duration)
        self._t = end

    async def beat(self, hold: float | None = None) -> None:
        """Record a pause point and advance the clock by exactly 1ms.

        The 1ms is not cosmetic. Ops apply when ``op.t <= t``, so without it
        content emitted after a beat would land on the same millisecond as
        the beat and be visible *at* the pause — the reveal would happen
        before the keypress that is supposed to trigger it.
        """
        hold_ms = self._beat_hold_ms if hold is None else int(hold * 1000)
        self._tl.beats.append(Beat(t=self._t, hold_ms=hold_ms))
        self._t += 1

    async def wait(self, seconds: float) -> None:
        """Advance the clock with nothing animating."""
        self._t += int(seconds * 1000)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scene.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add auditorium/scene.py tests/test_scene.py
git commit -m "feat(scene): compile-time clock, play/beat/wait, animate proxy"
```

---

### Task 3: Theme audit — every animation paused and persistent

Do this before writing `seek()`, so the runtime is built against themes that already satisfy its invariant rather than against ones that violate it.

**Files:**
- Modify: `auditorium/static/theme.css:146`
- Create: `tests/test_themes.py`

**Interfaces:**
- Consumes: nothing.
- Produces: no Python API. Establishes the invariant that no shipped CSS uses a bare `transition:` property.

- [ ] **Step 1: Write the failing test**

Create `tests/test_themes.py`:

```python
import re
from pathlib import Path

THEMES = Path(__file__).parent.parent / "auditorium" / "themes"
STATIC = Path(__file__).parent.parent / "auditorium" / "static"

# A bare `transition:` declaration, not the `--aud-transition:` custom property.
BARE_TRANSITION = re.compile(r"(?<!-)\btransition\s*:", re.MULTILINE)


def css_files():
    return sorted(THEMES.glob("*.css")) + sorted(STATIC.glob("*.css"))


def test_no_shipped_css_uses_a_bare_transition_property():
    """CSSTransitions vanish from getAnimations() the instant they finish.

    After that, a backward seek past them silently no-ops and the element
    strands at its end value. Persistent keyframes (fill: both) seek back
    exactly, so shipped CSS must use animations, never transitions.
    """
    offenders = []
    for path in css_files():
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if BARE_TRANSITION.search(line):
                offenders.append(f"{path.name}:{i}: {line.strip()}")
    assert offenders == [], "bare transition: found in shipped CSS:\n" + "\n".join(offenders)


def test_the_custom_property_is_not_mistaken_for_a_transition():
    """Guard the regex itself: --aud-transition: is a custom property, not a rule."""
    assert BARE_TRANSITION.search("--aud-transition: aud-fade;") is None
    assert BARE_TRANSITION.search("  transition: opacity 0.3s;") is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_themes.py -v`
Expected: `test_no_shipped_css_uses_a_bare_transition_property` FAILS, reporting `theme.css:146: transition: opacity 0.3s;`. The second test passes.

- [ ] **Step 3: Convert the one offending rule to a persistent keyframe**

In `auditorium/static/theme.css`, replace the `transition: opacity 0.3s;` declaration on the slide indicator (line 146) with a keyframe animation, and add the keyframes near the other `@keyframes` blocks:

```css
/* Slide indicator fade. A persistent keyframe, not a transition: a
   CSSTransition is dropped from getAnimations() once it finishes, which
   makes any backward seek past it a silent no-op. */
@keyframes audIndicatorFade {
    from { opacity: 0; }
    to   { opacity: 1; }
}
```

and on the `#slide-indicator` rule that currently carries `transition: opacity 0.3s;`, replace that one declaration with:

```css
    animation: audIndicatorFade 0.3s ease both;
```

Locate it with: `grep -n "slide-indicator" -A6 auditorium/static/theme.css`

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_themes.py -v`
Expected: 2 passed

- [ ] **Step 5: Verify the indicator still looks right**

Run: `uv run auditorium run examples/demo_deck.py`
Advance a few slides and confirm the slide indicator still fades rather than popping. Close the browser.

- [ ] **Step 6: Commit**

```bash
git add auditorium/static/theme.css tests/test_themes.py
git commit -m "fix(theme): persistent keyframe for the slide indicator

CSSTransitions leave getAnimations() on completion, breaking backward
seek. Bans bare transition: in shipped CSS and enforces it with a test."
```

---

### Task 4: `seek(t)` — the runtime

The crux of the whole design. Everything else is a wrapper around this.

**Files:**
- Create: `auditorium/static/engine.js`
- Create: `tests/test_engine_seek.py`
- Create: `tests/fixtures/engine_harness.html`

**Interfaces:**
- Consumes: the timeline JSON shape produced by `Timeline.to_dict()`.
- Produces: global `window.AuditoriumEngine` with `load(timelineDict)`, `seek(tMs)`, `reset()`, `registerTween(fn)`, and read-only `currentTime`.

- [ ] **Step 1: Write the test harness page**

Create `tests/fixtures/engine_harness.html`:

```html
<!DOCTYPE html>
<html>
<head>
<style>
  body { margin: 0; }
  #slide-root { position: relative; width: 800px; height: 600px; }
  #slide-root > div { position: absolute; top: 0; left: 0; }
  /* An infinite decorative animation on a pseudo-element, mirroring what
     terminal.css and neon.css ship. A private registry cannot see this. */
  #chrome::after {
    content: "_";
    animation: harnessBlink 1s steps(2, end) infinite;
  }
  @keyframes harnessBlink { 50% { opacity: 0; } }
</style>
</head>
<body>
  <div id="chrome"></div>
  <div id="slide-root"></div>
  <script type="module">
    import { AuditoriumEngine } from "/engine.js";
    window.AuditoriumEngine = AuditoriumEngine;
  </script>
</body>
</html>
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_engine_seek.py`:

```python
import json
from pathlib import Path

import pytest

from auditorium.timeline import Node, Op, Timeline, Track

FIXTURE = Path(__file__).parent / "fixtures" / "engine_harness.html"
ENGINE = Path(__file__).parent.parent / "auditorium" / "static" / "engine.js"


@pytest.fixture
def timeline_dict():
    """A box that fades in over 500ms, then slides 0 -> 500px over 1000ms."""
    tl = Timeline(meta={"title": "fixture"})
    tl.nodes.append(Node(id="n1", layer="dom", html="<div id='box'>box</div>"))
    tl.ops.append(Op(t=0, action="append", node="n1"))
    tl.tracks.append(Track(node="n1", prop="opacity", from_=0, to=1, start=0, end=500))
    tl.tracks.append(
        Track(node="n1", prop="transform.x", from_=0, to=500, start=500, end=1500)
    )
    return tl.to_dict()


async def serve(page, timeline_dict):
    """Load the harness with engine.js and the timeline, without a server."""
    engine_src = ENGINE.read_text()
    html = FIXTURE.read_text().replace(
        '<script type="module">\n    import { AuditoriumEngine } from "/engine.js";\n'
        "    window.AuditoriumEngine = AuditoriumEngine;\n  </script>",
        f"<script type='module'>\n{engine_src}\n"
        "window.AuditoriumEngine = AuditoriumEngine;\n</script>",
    )
    await page.set_content(html)
    await page.evaluate(
        "(tl) => window.AuditoriumEngine.load(tl)", json.loads(json.dumps(timeline_dict))
    )


async def x_of(page, selector="#n1"):
    return await page.evaluate(
        "(sel) => { const el = document.querySelector(sel);"
        " if (!el) return null;"
        " const m = new DOMMatrix(getComputedStyle(el).transform);"
        " return Math.round(m.m41); }",
        selector,
    )


async def opacity_of(page, selector="#n1"):
    return await page.evaluate(
        "(sel) => { const el = document.querySelector(sel);"
        " return el ? parseFloat(getComputedStyle(el).opacity) : null; }",
        selector,
    )


async def test_ops_apply_at_their_time(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    assert await browser_page.evaluate("() => !!document.querySelector('#n1')")


async def test_opacity_interpolates_at_the_midpoint(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(250)")
    assert 0.4 < await opacity_of(browser_page) < 0.6


async def test_a_finished_track_holds_its_end_value(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(1500)")
    assert await opacity_of(browser_page) == pytest.approx(1.0)
    assert await x_of(browser_page) == 500


async def test_a_track_that_has_not_started_holds_its_start_value(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(100)")
    assert await x_of(browser_page) == 0


async def test_seek_drives_pseudo_element_animations(browser_page, timeline_dict):
    """A private registry cannot see ::after. getAnimations() can."""
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(1200)")
    paused = await browser_page.evaluate(
        "() => document.getAnimations().every(a => a.playState === 'paused')"
    )
    assert paused is True
    times = await browser_page.evaluate(
        "() => document.getAnimations().map(a => a.currentTime)"
    )
    assert times and all(t == 1200 for t in times)


async def test_backward_seek_resets_and_replays(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(1500)")
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(250)")
    assert await x_of(browser_page) == 0
    assert 0.4 < await opacity_of(browser_page) < 0.6


async def test_ops_are_not_applied_twice_on_repeated_forward_seeks(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(10)")
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(20)")
    count = await browser_page.evaluate(
        "() => document.querySelectorAll('#slide-root > *').length"
    )
    assert count == 1


async def test_tween_callbacks_receive_the_current_time(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate(
        "() => { window.__seen = [];"
        " window.AuditoriumEngine.registerTween(t => window.__seen.push(t)); }"
    )
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(300)")
    assert await browser_page.evaluate("() => window.__seen.at(-1)") == 300


async def test_seek_is_path_independent(browser_page, timeline_dict):
    """Capture forward, seek to the end, re-capture. States must match.

    A 'render twice and compare' test cannot catch this — both runs travel
    forward. Seeking is genuinely path-dependent unless backward seeks reset.
    """
    await serve(browser_page, timeline_dict)
    probes = [0, 250, 500, 750, 1000, 1250, 1500]

    forward = []
    for t in probes:
        await browser_page.evaluate("(t) => window.AuditoriumEngine.seek(t)", t)
        forward.append((await opacity_of(browser_page), await x_of(browser_page)))

    await browser_page.evaluate("() => window.AuditoriumEngine.seek(3000)")

    again = []
    for t in probes:
        await browser_page.evaluate("(t) => window.AuditoriumEngine.seek(t)", t)
        again.append((await opacity_of(browser_page), await x_of(browser_page)))

    assert again == forward
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_engine_seek.py -v`
Expected: all FAIL — `engine.js` does not exist, so the module import in the harness throws and `window.AuditoriumEngine` is undefined.

- [ ] **Step 4: Write the implementation**

Create `auditorium/static/engine.js`:

```js
// The entire runtime. seek(t) puts the DOM into the state it holds at time t.
//
// Two invariants, both learned the hard way:
//
//   1. seek drives document.getAnimations(), never a private registry.
//      Themes ship infinite animations on pseudo-elements; a registry
//      structurally cannot see them, and unpaused they make every frame
//      nondeterministic.
//
//   2. Seeking is path-dependent. t=0 reached fresh differs from t=0
//      reached by rewinding. So seeking is only ever performed forward:
//      a backward seek resets to zero and replays.

const PROP_SETTERS = {
  "opacity": (from_, to) => [{ opacity: from_ }, { opacity: to }],
  "transform.x": (from_, to) => [
    { transform: `translateX(${from_}px)` },
    { transform: `translateX(${to}px)` },
  ],
  "transform.y": (from_, to) => [
    { transform: `translateY(${from_}px)` },
    { transform: `translateY(${to}px)` },
  ],
  "transform.scale": (from_, to) => [
    { transform: `scale(${from_})` },
    { transform: `scale(${to})` },
  ],
};

export const AuditoriumEngine = {
  _tl: null,
  _applied: 0,
  _t: -1,
  _tweens: [],
  _anchored: [],

  get currentTime() {
    return this._t;
  },

  load(timeline) {
    this._tl = timeline;
    this.reset();
  },

  registerTween(fn) {
    this._tweens.push(fn);
  },

  reset() {
    const root = document.getElementById("slide-root");
    if (root) root.innerHTML = "";
    this._applied = 0;
    this._t = 0;
    this._anchored = [];
  },

  seek(t) {
    if (this._tl === null) return;
    if (t < this._t) this.reset();

    // 1. Apply structural ops forward.
    const ops = this._tl.ops;
    while (this._applied < ops.length && ops[this._applied].t <= t) {
      this._applyOp(ops[this._applied]);
      this._applied += 1;
    }

    // 2. Position every animation on the page, including pseudo-elements
    //    and theme decoration the engine never created.
    for (const anim of document.getAnimations()) {
      anim.pause();
      anim.currentTime = t;
    }

    // 3. Anything WAAPI cannot interpolate.
    for (const fn of this._tweens) fn(t);

    // 4. Anchors: all reads, then all writes. Interleaving thrashes layout
    //    (182ms vs 9.9ms at 2000 anchors).
    this._resolveAnchors();

    this._t = t;
  },

  _applyOp(op) {
    const root = document.getElementById("slide-root");
    if (!root) return;
    if (op.action === "append") {
      const node = this._tl.nodes.find((n) => n.id === op.node);
      if (!node) return;
      const el = document.createElement("div");
      el.id = node.id;
      el.innerHTML = node.html || "";
      const parent =
        node.parent && node.parent !== "root"
          ? document.getElementById(node.parent) || root
          : root;
      parent.appendChild(el);
      this._attachTracks(node.id, el);
    } else if (op.action === "remove") {
      document.querySelectorAll(op.selector).forEach((el) => el.remove());
    } else if (op.action === "replace") {
      const el = document.querySelector(op.selector);
      if (el) el.innerHTML = op.html || "";
    } else if (op.action === "set_class") {
      const el = document.querySelector(op.selector);
      if (el) el.classList.add(...op.cls.split(/\s+/));
    } else if (op.action === "remove_class") {
      const el = document.querySelector(op.selector);
      if (el) el.classList.remove(...op.cls.split(/\s+/));
    }
  },

  _attachTracks(nodeId, el) {
    // Each track becomes one paused animation positioned on the GLOBAL
    // timeline via delay, with fill:both so it holds its start value before
    // it begins and its end value after it finishes. That is what lets a
    // single `currentTime = t` place every animation correctly.
    for (const track of this._tl.tracks) {
      if (track.node !== nodeId) continue;
      const build = PROP_SETTERS[track.prop];
      if (!build) continue;
      const keyframes = build(track.from, track.to);
      const anim = el.animate(keyframes, {
        delay: track.start,
        duration: Math.max(1, track.end - track.start),
        easing: track.ease || "linear",
        fill: "both",
      });
      anim.pause();
    }
  },

  _resolveAnchors() {
    if (this._anchored.length === 0) return;
    const reads = this._anchored.map((a) => ({
      spec: a,
      from: document.getElementById(a.fromId)?.getBoundingClientRect(),
      to: document.getElementById(a.toId)?.getBoundingClientRect(),
    }));
    for (const r of reads) {
      if (!r.from || !r.to) continue;
      r.spec.apply(r.from, r.to);
    }
  },
};
```

Note on `_attachTracks`: tracks attach when their node is appended, not at load, so a node that enters at t=2000 gets its animations only once it exists. Because animations use the global origin, a track attached late is still positioned correctly by the very next `currentTime` assignment in the same `seek` call.

`_resolveAnchors` is a stub with no producers until Stage 4; it ships now so the read/write phase separation is established before anything depends on it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_engine_seek.py -v`
Expected: 9 passed

- [ ] **Step 6: Prove the path-independence test can fail**

A test that cannot fail licenses shipping. Temporarily change `seek` to remove the reset:

```js
    if (t < this._t) this.reset();   // <- comment this line out
```

Run: `uv run pytest tests/test_engine_seek.py::test_seek_is_path_independent -v`
Expected: FAIL. Then restore the line and confirm it passes again. Do not commit the broken version.

- [ ] **Step 7: Commit**

```bash
git add auditorium/static/engine.js tests/test_engine_seek.py tests/fixtures/engine_harness.html
git commit -m "feat(engine): seek(t) runtime over document.getAnimations()

Backward seeks reset and replay forward; seeking is path-dependent.
Anchor resolution batches reads before writes."
```

---

### Task 5: Compile a deck to a timeline

**Files:**
- Create: `auditorium/compile.py`
- Create: `tests/test_compile.py`

**Interfaces:**
- Consumes: `auditorium.scene.SceneContext`, `auditorium.timeline.Timeline`, `auditorium.deck.Deck`.
- Produces: `async compile_deck(deck: Deck) -> Timeline`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_compile.py`:

```python
from auditorium.compile import compile_deck
from auditorium.deck import Deck


async def test_compiles_an_empty_deck():
    deck = Deck("Empty")
    tl = await compile_deck(deck)
    assert tl.meta["title"] == "Empty"
    assert tl.ops == []


async def test_compiles_a_single_scene():
    deck = Deck("One")

    @deck.scene
    async def intro(s):
        h = await s.show("<p>hi</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)

    tl = await compile_deck(deck)
    assert len(tl.nodes) == 1
    assert tl.tracks[0].end == 500


async def test_scenes_are_laid_end_to_end_on_one_clock():
    deck = Deck("Two")

    @deck.scene
    async def first(s):
        await s.wait(1.0)

    @deck.scene
    async def second(s):
        h = await s.show("<p>b</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)

    tl = await compile_deck(deck)
    # The scene boundary emits a beat at 1000, which advances the clock by 1ms.
    assert tl.ops[0].t == 1001
    assert (tl.tracks[0].start, tl.tracks[0].end) == (1001, 1501)


async def test_a_scene_boundary_emits_a_beat():
    deck = Deck("Two")

    @deck.scene
    async def first(s):
        await s.wait(1.0)

    @deck.scene
    async def second(s):
        await s.wait(1.0)

    tl = await compile_deck(deck)
    assert [b.t for b in tl.beats] == [1000]


async def test_python_computation_drives_the_timeline():
    """The point of compile-not-perform: real algorithms author animations."""
    deck = Deck("Sort")

    @deck.scene
    async def bubble(s):
        arr = [3, 1, 2]
        handles = [await s.show(f"<b>{v}</b>") for v in arr]
        for i in range(len(arr)):
            for j in range(len(arr) - i - 1):
                if arr[j] > arr[j + 1]:
                    arr[j], arr[j + 1] = arr[j + 1], arr[j]
                    await s.play(handles[j].animate.move_to(j * 50, 0), run_time=0.2)

    tl = await compile_deck(deck)
    assert len(tl.tracks) > 0
    assert tl.duration_ms > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_compile.py -v`
Expected: FAIL — no `auditorium.compile`, and `Deck` has no `scene` decorator.

- [ ] **Step 3: Add the `scene` decorator to Deck**

In `auditorium/deck.py`, add to the `Deck` class, directly after the existing `slide` method:

```python
    def scene(
        self,
        func: Callable | None = None,
        *,
        order: float | None = None,
        title: str | None = None,
    ) -> Callable:
        """Register an async function as a scene.

        Identical registration to ``slide``; the difference is which context
        object the compiler passes in — a full SceneContext rather than the
        restricted slide shim.
        """
        def decorator(fn: Callable) -> Callable:
            fn._auditorium_scene = True
            self._slides.append(SlideInfo(func=fn, title=title, order=order))
            return fn

        if func is not None:
            return decorator(func)
        return decorator
```

- [ ] **Step 4: Write the compiler**

Create `auditorium/compile.py`:

```python
"""Run a deck to produce a Timeline. Nothing is displayed and nothing sleeps."""
from __future__ import annotations

from auditorium.deck import Deck
from auditorium.scene import SceneContext
from auditorium.timeline import Timeline

SHIM_BEAT_HOLD_MS = 1500


async def compile_deck(deck: Deck) -> Timeline:
    """Execute every scene against a shared clock and return the timeline."""
    tl = Timeline(meta={"title": deck.title})
    ctx: SceneContext | None = None

    for index, info in enumerate(deck.slides):
        is_scene = getattr(info.func, "_auditorium_scene", False)
        hold = 0 if is_scene else SHIM_BEAT_HOLD_MS

        if ctx is None:
            ctx = SceneContext(tl, beat_hold_ms=hold)
        else:
            # Scene boundary: a beat, then continue on the same clock.
            ctx._beat_hold_ms = hold
            await ctx.beat()

        if is_scene:
            await info.func(ctx)
        else:
            from auditorium.slide import SlideContext
            await info.func(SlideContext(ctx))

    return tl
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_compile.py -v`
Expected: 5 passed. `test_python_computation_drives_the_timeline` is the one that matters — it is the whole thesis in one assertion.

- [ ] **Step 6: Commit**

```bash
git add auditorium/compile.py auditorium/deck.py tests/test_compile.py
git commit -m "feat(compile): run a deck to a timeline on a shared clock"
```

---

### Task 6: The compatibility shim

**Files:**
- Modify: `auditorium/slide.py` (constructor, and `step`/`sleep` at lines 240-273)
- Create: `tests/test_shim.py`

**Interfaces:**
- Consumes: `auditorium.scene.SceneContext`.
- Produces: `SlideContext(scene: SceneContext)` — same public vocabulary as before (`show`, `md`, `show_md`, `title`, `subtitle`, `section`, `block`, `hide`, `replace`, `set_class`, `remove_class`, `columns`, `rows`, `place`), with `step()` mapping to `beat()` and `sleep(x)` to `wait(x)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_shim.py`:

```python
import inspect

from auditorium.compile import compile_deck
from auditorium.deck import Deck
from auditorium.slide import SlideContext


async def test_step_becomes_a_beat():
    deck = Deck("D")

    @deck.slide
    async def one(ctx):
        await ctx.md("hello")
        await ctx.step()
        await ctx.md("world")

    tl = await compile_deck(deck)
    assert len(tl.beats) == 1


async def test_sleep_advances_the_clock_instead_of_blocking():
    import time
    deck = Deck("D")

    @deck.slide
    async def one(ctx):
        await ctx.sleep(5.0)
        await ctx.md("after")

    started = time.monotonic()
    tl = await compile_deck(deck)
    assert time.monotonic() - started < 0.5
    assert tl.ops[-1].t == 5000


async def test_shim_beats_get_a_nonzero_render_hold():
    """A slide deck rendered to video must not blast past its reveals."""
    deck = Deck("D")

    @deck.slide
    async def one(ctx):
        await ctx.step()

    tl = await compile_deck(deck)
    assert tl.beats[0].hold_ms == 1500


async def test_the_construction_vocabulary_is_unchanged():
    """These are timing-agnostic and must survive the rewrite verbatim."""
    expected = {
        "show", "md", "show_md", "title", "subtitle", "section", "block",
        "hide", "replace", "set_class", "remove_class",
        "columns", "rows", "place", "step", "sleep",
    }
    actual = {n for n, _ in inspect.getmembers(SlideContext, inspect.isfunction)
              if not n.startswith("_")}
    assert expected <= actual


async def test_the_export_fakery_is_gone():
    src = inspect.getsource(SlideContext)
    assert "instant_sleep" not in src
    assert "auto_step" not in src
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_shim.py -v`
Expected: FAIL — `SlideContext.__init__` still takes a `Presentation`, and `instant_sleep`/`auto_step` are still in the source.

- [ ] **Step 3: Rewrite the constructor and the two timing primitives**

In `auditorium/slide.py`, replace the constructor:

```python
class SlideContext:
    """Restricted SceneContext preserving the 3.x slide vocabulary.

    Construction methods are timing-agnostic and carry over verbatim; only
    step() and sleep() differ, and both now map onto timeline operations
    rather than blocking on a wall clock.
    """

    def __init__(self, scene) -> None:
        self._scene = scene
        self._target_stack: list[str] = []
```

Replace `step` and `sleep` (currently lines 240-273) in their entirety:

```python
    # --- Timing ---

    async def step(self) -> None:
        """Mark a keypress-gated pause point."""
        await self._scene.beat()

    async def sleep(self, seconds: float) -> None:
        """Advance the timeline by ``seconds``. Does not block."""
        await self._scene.wait(seconds)
```

Then rewrite every remaining reference to the old presentation object. Find them with:

```bash
grep -n "_pres" auditorium/slide.py
```

Each `await self._pres.send_mutation(mutation)` becomes `await self._scene._emit_op(mutation)`. There are no other uses of `self._pres` once `step` and `sleep` are replaced; if the grep shows any, they belong to code the shim no longer needs. Re-run the grep after editing and confirm it returns nothing.

- [ ] **Step 4: Add the op-emitting bridge to SceneContext**

In `auditorium/scene.py`, add to `SceneContext`:

```python
    async def _emit_op(self, mutation: dict) -> None:
        """Bridge for the slide shim: turn a 3.x mutation dict into an Op.

        The shim's construction vocabulary was written against a mutation
        protocol; rather than rewrite all of it, translate at this boundary.
        """
        action = mutation["action"]
        if action == "append":
            node_id = mutation.get("element_id") or self._next_id()
            self._tl.nodes.append(
                Node(id=node_id, layer="dom", html=mutation["html"],
                     parent=mutation.get("target", "root").lstrip("#"))
            )
            self._tl.ops.append(Op(t=self._t, action="append", node=node_id))
        else:
            self._tl.ops.append(
                Op(t=self._t, action=action, selector=mutation.get("selector"),
                   html=mutation.get("html"), cls=mutation.get("cls"))
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_shim.py tests/test_compile.py -v`
Expected: 10 passed

- [ ] **Step 6: Commit**

```bash
git add auditorium/slide.py auditorium/scene.py tests/test_shim.py
git commit -m "refactor(slide): SlideContext becomes a shim over SceneContext

step() -> beat(), sleep() -> wait(). Deletes the instant_sleep and
auto_step branches, which existed only to fake a timeline for export."
```

---

### Task 7: Server serves a timeline

**Files:**
- Modify: `auditorium/server.py` (delete `send_mutation`, `pending_acks`, `_run_slide`, `_handle_keypress`, `_go_to_slide`; rewrite `reload_deck`)
- Create: `tests/test_server.py`

**Interfaces:**
- Consumes: `auditorium.compile.compile_deck`.
- Produces: `create_app(deck, presenter_mode=False)` serving `GET /timeline.json` returning `Timeline.to_dict()`, and a `/ws` endpoint whose only message types are `{"type": "reload"}` (server→client) and `{"type": "hello"}` (client→server).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_server.py`:

```python
import inspect

from fastapi.testclient import TestClient

from auditorium import server
from auditorium.deck import Deck


def make_deck():
    deck = Deck("Served")

    @deck.scene
    async def intro(s):
        h = await s.show("<p>hi</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)

    return deck


def test_timeline_endpoint_returns_the_compiled_timeline():
    client = TestClient(server.create_app(make_deck()))
    body = client.get("/timeline.json").json()
    assert body["meta"]["title"] == "Served"
    assert body["meta"]["duration_ms"] == 500
    assert len(body["nodes"]) == 1


def test_index_still_serves_the_shell_with_theme_overrides():
    client = TestClient(server.create_app(make_deck()))
    html = client.get("/").text
    assert "<!--AUDITORIUM_THEME_OVERRIDES-->" not in html
    assert "slide-root" in html


def test_the_ack_protocol_is_gone():
    src = inspect.getsource(server)
    assert "pending_acks" not in src
    assert "send_mutation" not in src
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL — no `/timeline.json` route; `pending_acks` and `send_mutation` still present.

- [ ] **Step 3: Rewrite the server**

Replace the `Presentation` dataclass with a much smaller one — the per-mutation machinery is gone because playback is local to the browser:

```python
@dataclass
class Presentation:
    """Connected clients for one presentation. Playback happens in the browser."""

    audience_clients: list[WebSocket] = field(default_factory=list)
    presenter_ws: WebSocket | None = None

    async def send(self, message: dict) -> None:
        data = json.dumps(message)
        for ws in list(self.audience_clients):
            try:
                await ws.send_text(data)
            except Exception:
                self.audience_clients.remove(ws)
        if self.presenter_ws:
            try:
                await self.presenter_ws.send_text(data)
            except Exception:
                self.presenter_ws = None

    @property
    def has_clients(self) -> bool:
        return bool(self.audience_clients) or self.presenter_ws is not None
```

Add the timeline route inside `create_app`, after the `/presenter` route:

```python
    @app.get("/timeline.json")
    async def timeline_json() -> JSONResponse:
        if app.state.deck is None:
            return JSONResponse({"version": 1, "meta": {}, "nodes": [],
                                 "ops": [], "tracks": [], "beats": [], "audio": []})
        timeline = await compile_deck(app.state.deck)
        return JSONResponse(timeline.to_dict())
```

with imports at the top of the file:

```python
from fastapi.responses import HTMLResponse, JSONResponse

from auditorium.compile import compile_deck
```

Delete `_run_slide`, `_handle_keypress`, `_go_to_slide`, `Presentation.send_mutation`, `Presentation.replay_to`, `Presentation.cancel_slide`, and every field they used (`slide_task`, `step_event`, `numeric_buffer`, `pending_acks`, `auto_step`, `slide_delay`, `instant_sleep`, `_message_log`). Navigation now lives in the client.

In both `_handle_independent_session` and `_handle_shared_session`, delete the slide-starting block and reduce the message loop to a drain — navigation now lives in the client, so the server has nothing to do with incoming messages except keep the socket open:

```python
        while True:
            await ws.receive_text()  # drained; navigation is client-side
```

Delete the `auto_step` / `slide_delay` / `instant_sleep` parsing from the hello handler in `_handle_independent_session` (currently lines 166-174); those parameters described the old fake-timeline export path.

Then replace `reload_deck`:

```python
async def reload_deck(app: FastAPI, new_deck) -> None:
    """Hot-reload: swap the deck and tell clients to refetch the timeline."""
    app.state.deck = new_deck
    all_pres = list(app.state.sessions.values())
    if app.state.shared_pres:
        all_pres.append(app.state.shared_pres)
    for pres in all_pres:
        await pres.send({"type": "reload"})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_server.py -v`
Expected: 3 passed

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -v`
Expected: all green. If `test_toolchain.py` or `test_engine_seek.py` broke, the server change touched something it should not have.

- [ ] **Step 6: Commit**

```bash
git add auditorium/server.py tests/test_server.py
git commit -m "refactor(server): serve a compiled timeline, drop the ack protocol

Playback moves to the browser. The per-mutation round trip was the source
of the latency documented as a failure mode in design.md."
```

---

### Task 8: The present client

**Files:**
- Modify: `auditorium/static/index.html` (replace the mutation-applying client script)
- Create: `tests/test_present_client.py`

**Interfaces:**
- Consumes: `window.AuditoriumEngine`, `GET /timeline.json`.
- Produces: a `present` client that plays between beats and seeks on navigation keys.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_present_client.py`:

```python
import pytest
import uvicorn
import asyncio
import threading

from auditorium.deck import Deck
from auditorium.server import create_app


@pytest.fixture
async def live_server():
    deck = Deck("Live")

    @deck.scene
    async def one(s):
        h = await s.show("<p>first</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)
        await s.beat()
        h2 = await s.show("<p>second</p>")
        await s.play(h2.animate.fade_in(), run_time=0.5)

    config = uvicorn.Config(create_app(deck), host="127.0.0.1", port=8765,
                            log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        await asyncio.sleep(0.05)
    yield "http://127.0.0.1:8765"
    server.should_exit = True
    thread.join(timeout=5)


async def test_client_loads_the_timeline_and_renders_the_first_scene(browser_page, live_server):
    await browser_page.goto(live_server)
    await browser_page.wait_for_function(
        "() => window.AuditoriumEngine && window.AuditoriumEngine.currentTime >= 0"
    )
    await browser_page.wait_for_selector("#slide-root >> text=first")


async def test_space_advances_to_the_next_beat(browser_page, live_server):
    await browser_page.goto(live_server)
    await browser_page.wait_for_selector("#slide-root >> text=first")
    await browser_page.keyboard.press(" ")
    await browser_page.wait_for_selector("#slide-root >> text=second")


async def test_backward_navigation_works(browser_page, live_server):
    """D7 in the 2.0 design rejected this. A timeline makes it free."""
    await browser_page.goto(live_server)
    await browser_page.wait_for_selector("#slide-root >> text=first")
    await browser_page.keyboard.press(" ")
    await browser_page.wait_for_selector("#slide-root >> text=second")
    await browser_page.keyboard.press("ArrowLeft")
    await browser_page.wait_for_function(
        "() => !document.querySelector('#slide-root').textContent.includes('second')"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_present_client.py -v`
Expected: FAIL — `index.html` still runs the old mutation client and never defines `window.AuditoriumEngine`.

- [ ] **Step 3: Replace the client script in index.html**

In `auditorium/static/index.html`, delete the entire inline `<script>` block that implements the WebSocket mutation applier — it begins at the line containing `window.__auditorium_finished = false;` and runs to the matching `</script>`. Locate its bounds with:

```bash
grep -n "<script\|</script>\|__auditorium_finished" auditorium/static/index.html
```

Replace that whole block with:

```html
<script type="module">
import { AuditoriumEngine } from "/static/engine.js";
window.AuditoriumEngine = AuditoriumEngine;

let beats = [];
let duration = 0;
let playing = false;
let clockStart = 0;
let clockBase = 0;

async function loadTimeline() {
  const tl = await (await fetch("/timeline.json")).json();
  beats = (tl.beats || []).map((b) => b.t);
  duration = tl.meta.duration_ms || 0;
  AuditoriumEngine.load(tl);
  AuditoriumEngine.seek(0);
  playTo(nextBeat(0));
}

function nextBeat(from) {
  for (const b of beats) if (b > from) return b;
  return duration;
}

function prevBeat(from) {
  let target = 0;
  for (const b of beats) if (b < from - 1) target = b;
  return target;
}

function playTo(target) {
  playing = true;
  clockBase = AuditoriumEngine.currentTime;
  clockStart = performance.now();
  function frame(now) {
    if (!playing) return;
    const t = Math.min(clockBase + (now - clockStart), target);
    AuditoriumEngine.seek(t);
    if (t < target) requestAnimationFrame(frame);
    else playing = false;
  }
  requestAnimationFrame(frame);
}

document.addEventListener("keydown", (e) => {
  const t = AuditoriumEngine.currentTime;
  if (e.key === " " || e.key === "ArrowRight") {
    e.preventDefault();
    if (playing) { playing = false; AuditoriumEngine.seek(nextBeat(t)); }
    else playTo(nextBeat(t));
  } else if (e.key === "ArrowLeft") {
    e.preventDefault();
    playing = false;
    AuditoriumEngine.seek(prevBeat(t));
  } else if (e.key === "r") {
    e.preventDefault();
    playing = false;
    AuditoriumEngine.seek(0);
  }
});

const ws = new WebSocket(`ws://${location.host}/ws`);
ws.onopen = () => ws.send(JSON.stringify({ type: "hello", role: "audience" }));
ws.onmessage = (ev) => {
  if (JSON.parse(ev.data).type === "reload") loadTimeline();
};

loadTimeline();
</script>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_present_client.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add auditorium/static/index.html tests/test_present_client.py
git commit -m "feat(present): client plays a local timeline, backward nav works"
```

---

### Task 9: Existing decks run on the new runtime

`CLAUDE.md` makes `examples/demo_deck.py` living documentation: it must contain every feature and run smoothly. This task is the gate that proves the shim did its job, and it is the one that decides whether Stage 1 is done.

**Files:**
- Modify: `pyproject.toml` (version), `auditorium/cli.py` (version string)
- Modify: `examples/demo_deck.py` (add one scene exercising `play`/`beat`)
- Create: `tests/test_examples.py`

**Interfaces:**
- Consumes: everything above.
- Produces: no new API.

- [ ] **Step 1: Write the failing test**

Create `tests/test_examples.py`:

```python
from pathlib import Path

import pytest

from auditorium.cli import _load_deck
from auditorium.compile import compile_deck

EXAMPLES = Path(__file__).parent.parent / "examples"


def example_decks():
    return sorted(EXAMPLES.glob("*.py")) + sorted(EXAMPLES.glob("showcase/*.py"))


@pytest.mark.parametrize("path", example_decks(), ids=lambda p: p.name)
async def test_every_example_deck_compiles(path):
    """Every shipped deck must survive the move to the scene engine."""
    deck = _load_deck(path)
    timeline = await compile_deck(deck)
    assert timeline.duration_ms >= 0
    assert timeline.ops, f"{path.name} compiled to an empty timeline"


async def test_demo_deck_exercises_the_animation_vocabulary():
    """demo_deck.py is living documentation; new primitives must appear in it."""
    source = (EXAMPLES / "demo_deck.py").read_text()
    assert "@deck.scene" in source
    assert ".animate." in source
    assert "s.play(" in source
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_examples.py -v`
Expected: `test_demo_deck_exercises_the_animation_vocabulary` FAILS. The compile tests may pass or fail; any failure there is a genuine shim gap and must be fixed, not worked around.

- [ ] **Step 3: Fix any deck that fails to compile**

For each failing deck, the cause will be a construction method still reaching for `self._pres`. Fix it in `slide.py`, not in the example.

- [ ] **Step 4: Add an animation scene to the demo deck**

Append to `examples/demo_deck.py`:

```python
@deck.scene(title="Animation")
async def animation(s):
    """Scenes: timed animation with `play`, paced by `beat`."""
    await s.title("Animation")
    box = await s.show("<div class='aud-block aud-block-info'>I move</div>")
    await s.play(box.animate.fade_in(), run_time=0.4)
    await s.beat()
    await s.play(box.animate.move_to(300, 0), run_time=0.8, ease="out-cubic")
    await s.play(box.animate.scale_to(1.4), run_time=0.4, ease="out-back")
```

- [ ] **Step 5: Bump the version**

In `pyproject.toml`: `version = "1!4.0.0a1"`. In `auditorium/cli.py`, update the version string reported by `--version` to match. An alpha, not the release — `record`, `export`, and `--presenter` are still broken until Stage 3.

- [ ] **Step 6: Run the whole suite**

Run: `uv run pytest -v`
Expected: all green.

- [ ] **Step 7: Verify by hand, the way a user reaches it**

Run: `uv run auditorium run examples/demo_deck.py`

Walk every slide. Confirm: content appears, space advances, **left arrow now goes back**, the new Animation scene moves and scales, and themes still render. Then run one showcase deck with a theme that has an infinite pseudo-element animation:

Run: `uv run auditorium run examples/showcase/<terminal-theme-deck>.py`

Confirm the blinking cursor still blinks during playback and does not freeze.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml auditorium/cli.py examples/demo_deck.py tests/test_examples.py
git commit -m "feat: auditorium 4.0 — every example deck on the scene engine"
```

---

## Stage 1 done when

- `uv run pytest` is green.
- Every deck in `examples/` compiles to a non-empty timeline.
- `demo_deck.py` demonstrates `@deck.scene`, `play`, `beat`, and `.animate`.
- Backward navigation works in `present`.
- `grep -rn "instant_sleep\|auto_step\|pending_acks\|send_mutation" auditorium/` returns nothing.

Stages 2 (preview client), 3 (renderer), and 4 (SVG layer) get their own plans, written once these interfaces are real rather than predicted.

## Deliberately not in Stage 1

Four surfaces will be **broken** at the end of this stage. This is intended, and it is listed here so the breakage is not mistaken for a regression:

- **`auditorium record`** and **`auditorium export`** — both drive the deleted `_run_slide` path. `render.py` replaces `recorder.py` in Stage 3, and `exporter.py` is rewritten there to seek to beats.
- **The presenter view** (`static/presenter.html`, `auditorium/relay.py`) — it consumes the `clear` / `slide` / `notes` / `next_preview` messages that Task 7 deletes. Rebuilding it over the timeline is genuinely separable work: notes and next-slide previews become timeline metadata rather than pushed messages, and the presenter becomes a third thin client alongside `present` and `preview`. It belongs with Stage 2, where the second client is built anyway.

Do not patch any of these to keep them alive through Stage 1 — propping them against a runtime that is about to be replaced is wasted work. Say so plainly in the Task 7 commit message.

A consequence worth stating: at the end of Stage 1 the repo is *shippable* in the sense that `auditorium run` works and every example deck plays, but it is **not releasable** to PyPI, because `record`, `export`, and `--presenter` are advertised features that will not work. Do not tag `1!4.0.0` until Stage 3 lands.
