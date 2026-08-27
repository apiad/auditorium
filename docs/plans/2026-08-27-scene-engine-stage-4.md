# Auditorium 4.0 Scene Engine — Stage 4 (The SVG layer) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the geometric layer — `Line`, `Arrow`, `Path`, `Circle` — with symbolic anchors that track DOM nodes through motion and reflow, and stroke draw-on animation. This is what makes an algorithm visualisation drawable and is the last stage of the 4.0 spec.

**Architecture:** SVG nodes live in a full-viewport overlay sharing the viewport coordinate space with the DOM layer, so `getBoundingClientRect()` values are directly usable as SVG coordinates and Python never models layout (D6). An anchor is a symbolic reference — `arrow.from = box.right` — resolved in the browser at seek time, in one batched read phase followed by one batched write phase, because interleaving costs 182 ms/frame at 2000 anchors against a 33 ms budget. Draw-on animates `stroke-dashoffset` in normalized units via `pathLength="1"`, which sidesteps measuring geometry that anchors may be about to change.

**Tech Stack:** Python 3.12+, vanilla ES modules, SVG 1.1 (`createElementNS`), WAAPI, Playwright (Chromium 1234), pytest.

**Spec:** `docs/design/2026-08-26-scene-engine.md` (see "The scene graph", D6, and the "SVG path morphing" open question)

> **Status: complete, 2026-08-27.** Landed in `1!4.0.0`.
> Two things the plan did not anticipate: screen rects need converting into the
> overlay's user units via `getScreenCTM` (the preview and presenter both scale
> their stage), and the `clear` op has to empty the overlay as well as the slide
> root. Path morphing is deferred rather than degraded to a cross-fade.

**Predecessors:** Stages 1, 2 and 3 complete. `engine.js` already carries an empty `_anchored` list and a `_resolveAnchors()` that reads-then-writes — this stage fills them.

## Global Constraints

- **Committing in a shared checkout.** `git add <explicit paths> && git commit -m "msg" -- <the same paths>`. Never `git add -A`/`.`/`-u`, `--amend`, `git stash`, or `git checkout` a path this task did not create.
- **Reads before writes, always** (D6). Any code that calls `getBoundingClientRect()` inside a loop that also writes SVG attributes is a defect even when it looks correct, because it only shows up as a frame-budget overrun on dense scenes — the exact scenes this layer exists for.
- **Python computes no layout.** No stage may resolve an anchor to a number in Python. If a task finds itself importing a geometry helper, the design has gone wrong.
- **`seek(t)` remains the only runtime primitive** (D2). SVG geometry updates happen inside `seek`, never on a separate rAF loop or a `ResizeObserver`.
- **Every animation is paused and `fill: both`** (D3). Draw-on is no exception.
- All timeline times are integer milliseconds. Anchors are resolved every seek — they are never cached across frames, because the DOM node may have moved.
- English for code, comments, identifiers, commit messages, and test names.

---

### Task 1: SVG nodes in the timeline

The timeline is the contract, so the geometry vocabulary lands there first — pure data, no browser, testable in isolation.

**Files:**
- Create: `auditorium/nodes.py`
- Modify: `auditorium/timeline.py` (`Node` carries an optional `svg` payload)
- Test: `tests/test_nodes.py`, `tests/test_timeline.py`

**Interfaces:**
- Produces `auditorium.nodes`:
  - `Anchor(node: str, side: str)` where side ∈ `{"left","right","top","bottom","center"}`; `to_dict()` → `{"node": ..., "side": ...}`.
  - `Line(from_, to, *, stroke="currentColor", width=2, dash=None)`
  - `Arrow(from_, to, *, stroke="currentColor", width=2, head=10)`
  - `Circle(at, r, *, stroke="currentColor", width=2, fill="none")`
  - `Path(d, *, stroke="currentColor", width=2, fill="none")`
  - Each exposes `to_svg_dict() -> dict` with a `"kind"` key (`"line" | "arrow" | "circle" | "path"`) plus its own fields. Endpoints serialize as either `{"anchor": {...}}` or `{"point": [x, y]}`.
- Modifies `timeline.Node`: new field `svg: dict | None = None`, serialized under `"svg"`. `layer` is already there and becomes meaningful (`"dom"` vs `"svg"`).

- [x] **Step 1: Write the failing tests**

`tests/test_nodes.py`:

```python
def test_a_line_between_two_anchors_serializes_symbolically():
    line = Line(from_=Anchor("n1", "right"), to=Anchor("n2", "left"))
    d = line.to_svg_dict()
    assert d["kind"] == "line"
    assert d["from"] == {"anchor": {"node": "n1", "side": "right"}}
    assert d["to"] == {"anchor": {"node": "n2", "side": "left"}}


def test_a_line_between_two_points_serializes_literally():
    d = Line(from_=(10, 20), to=(30, 40)).to_svg_dict()
    assert d["from"] == {"point": [10, 20]}


def test_an_unknown_anchor_side_is_rejected_at_construction():
    with pytest.raises(ValueError, match="side"):
        Anchor("n1", "northeast")


def test_svg_nodes_round_trip_through_json():
    tl = Timeline()
    tl.nodes.append(Node(id="s1", layer="svg",
                         svg=Arrow(from_=Anchor("n1", "right"), to=(400, 300)).to_svg_dict()))
    back = Timeline.from_dict(json.loads(json.dumps(tl.to_dict())))
    assert back.nodes[0].layer == "svg"
    assert back.nodes[0].svg["kind"] == "arrow"
```

Rejecting a bad side at construction is worth a test: the alternative is an arrow that silently does not render, three layers away from the typo.

- [x] **Step 2: Run and watch fail.** `uv run pytest tests/test_nodes.py -q` → `ModuleNotFoundError`.

- [x] **Step 3: Implement `nodes.py` and the `Node.svg` field.**

Endpoint normalization is one shared helper:

```python
def _endpoint(value) -> dict:
    """Normalize an endpoint to either a symbolic anchor or a literal point.

    A tuple is a fixed viewport coordinate; an Anchor is a promise the
    browser keeps at seek time. Python never turns the second into the first.
    """
    if isinstance(value, Anchor):
        return {"anchor": value.to_dict()}
    x, y = value
    return {"point": [x, y]}
```

- [x] **Step 4: Run and watch pass.** `uv run pytest tests/test_nodes.py tests/test_timeline.py -q`

- [x] **Step 5: Commit**

```bash
git add auditorium/nodes.py auditorium/timeline.py tests/test_nodes.py tests/test_timeline.py
git commit -m "feat(nodes): geometric scene nodes with symbolic anchors" -- auditorium/nodes.py auditorium/timeline.py tests/test_nodes.py tests/test_timeline.py
```

---

### Task 2: The authoring surface — `draw()` and anchor properties

**Files:**
- Modify: `auditorium/scene.py` (`SceneContext.draw`, `NodeHandle` anchor properties, `AnimateProxy.draw_on`)
- Test: `tests/test_scene.py`

**Interfaces:**
- Consumes: `auditorium.nodes` (Task 1).
- Produces:
  - `await s.draw(shape) -> NodeHandle` — appends an svg-layer node and an `append` op at the current clock.
  - `NodeHandle.left/right/top/bottom/center -> Anchor`
  - `AnimateProxy.draw_on() -> list[AnimSpec]` emitting prop `"stroke.dashoffset"` from `1.0` to `0.0`.

- [x] **Step 1: Write the failing tests** in `tests/test_scene.py`:

```python
async def test_draw_appends_an_svg_node_at_the_current_clock():
    tl = Timeline()
    s = SceneContext(tl)
    await s.wait(2.0)
    handle = await s.draw(Circle(at=(100, 100), r=20))
    node = next(n for n in tl.nodes if n.id == handle.id)
    assert node.layer == "svg"
    assert [o.t for o in tl.ops if o.node == handle.id] == [2000]


async def test_a_handle_yields_anchors_on_every_side():
    s = SceneContext(Timeline())
    box = await s.show("<div>x</div>")
    assert box.right.node == box.id and box.right.side == "right"


async def test_draw_on_animates_dashoffset_to_zero():
    tl = Timeline()
    s = SceneContext(tl)
    line = await s.draw(Line(from_=(0, 0), to=(100, 0)))
    await s.play(line.animate.draw_on(), run_time=0.5)
    track = next(t for t in tl.tracks if t.node == line.id)
    assert (track.prop, track.from_, track.to) == ("stroke.dashoffset", 1.0, 0.0)
    assert (track.start, track.end) == (0, 500)
```

- [x] **Step 2: Run and watch fail.**

- [x] **Step 3: Implement.** `draw()` mirrors `show()`'s bookkeeping but sets `layer="svg"` and `svg=shape.to_svg_dict()`, and always parents to the overlay rather than the current region — an SVG node has viewport coordinates, so region scoping would be a lie.

- [x] **Step 4: Run and watch pass. Step 5: Commit**

```bash
git add auditorium/scene.py tests/test_scene.py
git commit -m "feat(scene): draw() and anchor properties on node handles" -- auditorium/scene.py tests/test_scene.py
```

---

### Task 3: The overlay and anchor resolution in the engine

The stage where the interesting failures live.

**Files:**
- Modify: `auditorium/static/engine.js`
- Modify: `auditorium/static/index.html`, `preview.html`, `presenter.html` (the overlay element + `<defs>`)
- Modify: `auditorium/static/theme.css` (overlay positioning — add rules only; another agent is editing this file)
- Modify: `tests/fixtures/engine_harness.html`
- Test: `tests/test_engine_svg.py`

**Interfaces:**
- Consumes: `Node.layer === "svg"` and `Node.svg` (Task 1).
- Produces: `AuditoriumEngine` handles svg-layer appends, populates `_anchored`, and resolves geometry inside `seek`. `PROP_SETTERS` gains `"stroke.dashoffset"`.

- [x] **Step 1: Write the failing tests** in `tests/test_engine_svg.py`:

```python
async def test_an_svg_node_appears_in_the_overlay_not_the_slide_root()
async def test_an_anchored_line_starts_at_the_right_edge_of_its_source()
async def test_the_anchor_follows_the_node_when_the_node_animates()
async def test_an_arrow_gets_a_head_marker()
async def test_draw_on_leaves_the_stroke_fully_hidden_at_its_start()
async def test_draw_on_leaves_the_stroke_fully_drawn_after_it_finishes()
async def test_reset_clears_the_overlay_and_the_anchor_registry()
async def test_anchor_resolution_reads_every_rect_before_writing_any()
```

`test_the_anchor_follows_the_node_when_the_node_animates` is the claim that justifies the whole symbolic-anchor design: seek to t=0, read the line's `x1`; seek to the end of a `move_to` on the anchored box; read `x1` again; assert it moved by the same delta the box did. An anchor that resolves once at append time passes every other test in this list and fails this one.

`test_anchor_resolution_reads_every_rect_before_writing_any` is the D6 guard, and it needs a structural test rather than a timing one — timing tests on a loaded machine are noise. Instrument by patching `Element.prototype.getBoundingClientRect` and the SVG attribute setter to push labels onto a global array, seek once with three anchored lines, then assert the array is all reads followed by all writes with no interleaving. A benchmark would prove today's machine was fast; this proves the property.

- [x] **Step 2: Run and watch fail.**

- [x] **Step 3: Add the overlay to the three client shells and the harness**

```html
<svg id="svg-layer" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="aud-arrowhead" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/>
    </marker>
  </defs>
</svg>
```

CSS: `#svg-layer { position: fixed; inset: 0; width: 100vw; height: 100vh; pointer-events: none; overflow: visible; }` and **no `viewBox`** — the overlay must map 1:1 to viewport pixels or `getBoundingClientRect()` values would need transforming, which is exactly the layout modelling D6 forbids.

`fill="context-stroke"` makes the head inherit the line's stroke; check it renders under Chromium 1234 and fall back to setting the marker's fill per-arrow if it does not.

- [x] **Step 4: Teach `_applyOp` about the svg layer**

Branch on `node.layer === "svg"` before the DOM path. Build with `createElementNS("http://www.w3.org/2000/svg", tag)` — `innerHTML` on an HTML parent produces HTML elements with SVG names, which look right in the inspector and never render. Map `kind` → tag (`line`, `path`, `circle`; `arrow` → `line` plus `marker-end="url(#aud-arrowhead)"`).

Set `pathLength="1"` and `stroke-dasharray="1"` on every stroked shape at creation, so draw-on works in normalized units and never has to measure a geometry that anchors may change on the next frame. Default `stroke-dashoffset` to `0` (fully drawn); a shape only hides itself if a `draw_on` track says so.

Register anchored endpoints:

```javascript
      if (fromA || toA) {
        this._anchored.push({ el, from: fromA, to: toA, kind: node.svg.kind });
      }
```

- [x] **Step 5: Implement `_resolveAnchors` for real**

Keep the existing two-phase shape and extend it: phase one collects, for every registered spec, the rects of whichever endpoints are symbolic (a literal point needs no read); phase two writes. The side→point reduction is pure arithmetic on an already-read rect and belongs in phase two:

```javascript
  _pointOn(rect, side) {
    switch (side) {
      case "left":   return [rect.left, rect.top + rect.height / 2];
      case "right":  return [rect.right, rect.top + rect.height / 2];
      case "top":    return [rect.left + rect.width / 2, rect.top];
      case "bottom": return [rect.left + rect.width / 2, rect.bottom];
      default:       return [rect.left + rect.width / 2, rect.top + rect.height / 2];
    }
  },
```

- [x] **Step 6: Add `"stroke.dashoffset"` to `PROP_SETTERS`**

```javascript
  "stroke.dashoffset": (from_, to) => [
    { strokeDashoffset: String(from_) },
    { strokeDashoffset: String(to) },
  ],
```

`composite` stays `"replace"` — the additive path in `_attachTracks` is scoped to transforms on purpose, and an additive dashoffset would sum against the base and clamp.

- [x] **Step 7: Extend `reset()`** to empty the overlay of everything except `<defs>`, and to clear `_anchored`. Forgetting `<defs>` deletes the arrowhead on the first rewind and every arrow after that renders headless.

- [x] **Step 8: Run and watch pass.** `uv run pytest tests/test_engine_svg.py -q`

- [x] **Step 9: Mutation-test the two structural claims**

Change `_resolveAnchors` to interleave reads and writes; confirm the D6 test fails. Change `_applyOp` to resolve anchors once at append instead of registering them; confirm the follow-the-node test fails. Restore both. A structural test that cannot fail is worth less than none.

- [x] **Step 10: Commit**

```bash
git add auditorium/static/engine.js auditorium/static/index.html auditorium/static/preview.html auditorium/static/presenter.html auditorium/static/theme.css tests/fixtures/engine_harness.html tests/test_engine_svg.py
git commit -m "feat(engine): svg overlay with browser-resolved anchors and draw-on" -- <the same paths>
```

---

### Task 4: The layer survives a render

An SVG layer that only works interactively is half a feature: the point of 4.0 is video.

**Files:**
- Create: `tests/fixtures/svg_scene.py` (a scene deck: two boxes, an anchored arrow, a `move_to`, a `draw_on`)
- Test: `tests/test_render_svg.py`

- [x] **Step 1: Write the test**

Render the fixture at a small size to a png-sequence, then assert on the *frames*: the frame at the start of the draw-on differs from the frame at its end, and the frame after the `move_to` differs from the frame before. Compare file bytes — a PNG that is byte-identical across an animation is the failure this catches, and it is the failure an "it rendered without erroring" check misses entirely.

- [x] **Step 2: Run, fix whatever the browser actually does, run again.**

Two failures are likely enough to plan for. Playwright's screenshot may not composite a `position: fixed` overlay the way the live page does — if so, the overlay becomes `position: absolute` on a positioned root. And `context-stroke` may be unsupported, in which case the arrowhead gets an explicit fill.

- [x] **Step 3: Commit**

```bash
git add tests/fixtures/svg_scene.py tests/test_render_svg.py
git commit -m "test(render): the svg layer renders and animates in video" -- tests/fixtures/svg_scene.py tests/test_render_svg.py
```

---

### Task 5: Living documentation

`examples/demo_deck.py` must contain every feature (CLAUDE.md). A geometric layer that no example exercises will rot.

**Files:**
- Modify: `examples/demo_deck.py` (a `@deck.scene` demonstrating anchors and draw-on)
- Modify: `Readme.md` (a geometry section)
- Modify: `CLAUDE.md` (`nodes.py` under "Key modules")
- Modify: `docs/design/2026-08-26-scene-engine.md` (status; resolve or restate the path-morphing open question with what was actually tried)

- [x] **Step 1: Add the scene**, run `uv run auditorium run examples/demo_deck.py`, walk to it, and look at it. Screenshot it.
- [x] **Step 2: Document it.** State plainly in the Readme what the layer does *not* do — path morphing between differing command counts is not in v1 — rather than leaving a reader to discover it.
- [x] **Step 3: Commit.**

---

### Task 6: Release gate

- [x] **Step 1: Full suite, unpiped, its own tool call.** `uv run pytest -q`
- [x] **Step 2: Render the demo deck end to end** and probe the artifact for the expected packet count.
- [x] **Step 3: Version to `1!4.0.0`** in `pyproject.toml` and `cli.py` — both, they are separate strings and one has been missed before.
- [x] **Step 4: CHANGELOG, spec status `implemented`, journal, release the lock.**
