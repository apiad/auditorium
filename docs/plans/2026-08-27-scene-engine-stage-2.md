# Auditorium 4.0 Scene Engine — Stage 2 (The clients) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the two remaining client surfaces over the compiled timeline — the `preview` authoring client (scrubber, frame stepping, loop-a-range, position-holding hot reload) and a rebuilt `presenter` view — so that `--presenter` stops being a broken advertised feature and 4.0 can be tagged honestly.

**Architecture:** Both clients are thin wrappers over `AuditoriumEngine.seek(t)`, exactly as the audience client already is (D2, D8). Neither gets its own state model. The presenter regains shared navigation by broadcasting *intent* (`seek t`, `play from→to`) rather than positions — every surface runs the same deterministic engine over the same timeline, so a command is enough and per-frame chatter is not needed. Speaker notes return to the timeline as a new `markers` list: one entry per scene carrying `t`, `title` and rendered docstring HTML.

**Tech Stack:** Python 3.12+, FastAPI, Playwright (Chromium 1234), vanilla ES modules, pytest + pytest-asyncio.

**Spec:** `docs/design/2026-08-26-scene-engine.md` (see "The clients", D2, D8, and the "Hot-reload holding position" open question)

> **Status: complete, 2026-08-27.** Landed as `1!4.0.0`; 141 passed, 1 skipped.
> Two things the plan did not anticipate and the work forced out: the frame
> readout had to report *rendered* frames rather than timeline frames, and the
> audience had to stop autoplaying in presenter mode (learning the mode from the
> shell, not the socket, so it is known before the first frame).

**Predecessors:** `docs/plans/2026-08-27-scene-engine-stage-1.md` (engine, `1!4.0.0a1`), `docs/plans/2026-08-27-scene-engine-stage-3.md` (renderer, `1!4.0.0b1`). Both complete.

## Global Constraints

- **Committing in a shared checkout.** Concurrent agents share one working tree and index. Every commit step uses:
  ```bash
  git add <explicit paths> && git commit -m "message" -- <the same explicit paths>
  ```
  Never `git add -A`, `git add .`, `git add -u`, `--amend`, `git stash`, or `git checkout`/`restore` on a path this task did not create. `auditorium/static/theme.css` and `uv.lock` are dirty with another agent's work — leave every hunk you did not write.
- **`seek(t)` stays the only runtime primitive** (D2). No client may compute DOM state by any other route. A client that "optimises" by mutating the DOM directly is a spec violation, not a shortcut.
- **Seeking is forward-only** (D5). Backward navigation resets and replays; that is the engine's job, and no client may work around it.
- **Bare `transition:` is banned in shipped CSS** (D3) and `tests/test_themes.py` enforces it. Any CSS added by this stage must pass that lint.
- All timeline times are integer milliseconds.
- Playwright stays an optional dependency: importing `auditorium.server` must never require it.
- English for code, comments, identifiers, commit messages, and test names.

---

### Task 1: Markers — speaker notes return to the timeline

The 3.x server sent a `notes` message per slide, read from the slide function's docstring. 4.0 dropped the protocol and the notes with it, so `compile_deck` currently discards `func.__doc__` entirely. The presenter cannot be rebuilt until the notes are back, and the timeline is where they belong: pure data, JSON-serializable, one entry per scene.

**Files:**
- Modify: `auditorium/timeline.py` (add `Marker`, wire into `Timeline`)
- Modify: `auditorium/compile.py` (emit one marker per slide/scene)
- Test: `tests/test_timeline.py`, `tests/test_compile.py`

**Interfaces:**
- Produces: `auditorium.timeline.Marker(t: int, title: str, notes_html: str = "")` with `to_dict()`/`from_dict()`; `Timeline.markers: list[Marker]`; the serialized key is `"markers"`, each entry `{"t", "title", "notes_html"}`.
- Consumes: `Deck.slides` → `SlideInfo.name` (title) and `SlideInfo.func.__doc__` (notes source, rendered with `markdown.markdown`).

- [x] **Step 1: Write the failing tests**

In `tests/test_timeline.py`:

```python
def test_markers_round_trip_through_json():
    tl = Timeline(meta={"title": "T"})
    tl.markers.append(Marker(t=0, title="Intro", notes_html="<p>hi</p>"))
    tl.markers.append(Marker(t=2500, title="Body"))
    back = Timeline.from_dict(json.loads(json.dumps(tl.to_dict())))
    assert [(m.t, m.title, m.notes_html) for m in back.markers] == [
        (0, "Intro", "<p>hi</p>"),
        (2500, "Body", ""),
    ]


def test_markers_do_not_extend_the_duration():
    tl = Timeline()
    tl.ops.append(Op(t=100, action="clear"))
    tl.markers.append(Marker(t=9999, title="stray"))
    assert tl.duration_ms == 100
```

In `tests/test_compile.py`:

```python
async def test_each_slide_contributes_one_marker_at_its_start():
    deck = Deck("D")

    @deck.slide
    async def first(ctx):
        """Opening remarks."""
        await ctx.title("One")
        await ctx.step()

    @deck.slide(title="Second slide")
    async def second(ctx):
        await ctx.title("Two")

    tl = await compile_deck(deck)
    assert [m.title for m in tl.markers] == ["first", "Second slide"]
    assert tl.markers[0].t == 0
    # The second marker sits at the boundary clear, not before it.
    clear_t = [o.t for o in tl.ops if o.action == "clear"][0]
    assert tl.markers[1].t == clear_t


async def test_the_docstring_becomes_rendered_notes():
    deck = Deck("D")

    @deck.slide
    async def only(ctx):
        """Remember the **punchline**."""
        await ctx.title("x")

    tl = await compile_deck(deck)
    assert "<strong>punchline</strong>" in tl.markers[0].notes_html


async def test_a_slide_without_a_docstring_has_empty_notes():
    deck = Deck("D")

    @deck.slide
    async def only(ctx):
        await ctx.title("x")

    tl = await compile_deck(deck)
    assert tl.markers[0].notes_html == ""
```

- [x] **Step 2: Run the tests and watch them fail**

Run: `uv run pytest tests/test_timeline.py tests/test_compile.py -q`
Expected: FAIL — `ImportError: cannot import name 'Marker'`.

- [x] **Step 3: Add `Marker` to the timeline**

In `auditorium/timeline.py`, after `Beat`:

```python
@dataclass
class Marker:
    """A named point on the timeline: where a scene begins, and its notes.

    Carries what the presenter view needs and nothing the engine does —
    ``seek`` ignores markers entirely, and they do not extend the duration.
    """
    t: int
    title: str
    notes_html: str = ""

    def to_dict(self) -> dict:
        return {"t": self.t, "title": self.title, "notes_html": self.notes_html}

    @classmethod
    def from_dict(cls, d: dict) -> Marker:
        return cls(t=d["t"], title=d.get("title", ""),
                   notes_html=d.get("notes_html", ""))
```

Add `markers: list[Marker] = field(default_factory=list)` to `Timeline`, serialize it in `to_dict` (`"markers": [m.to_dict() for m in self.markers]`), and restore it in `from_dict`. Do **not** add markers to `duration_ms`'s candidates: a marker is a label on time, not an extent of it.

- [x] **Step 4: Emit markers in `compile_deck`**

In `auditorium/compile.py`, import `Marker` and `markdown`. Immediately before dispatching each slide/scene body (i.e. after the boundary `beat()` + `clear()` for slides after the first), append:

```python
        tl.markers.append(Marker(
            t=ctx.t_ms,
            title=info.name,
            notes_html=_notes_html(info.func),
        ))
```

with the helper:

```python
def _notes_html(func) -> str:
    """Render a scene function's docstring as speaker notes.

    Dedented because a docstring's continuation lines carry the source
    indentation, and markdown reads four leading spaces as a code block.
    """
    doc = inspect.getdoc(func)
    return markdown.markdown(doc, extensions=["extra"]) if doc else ""
```

`inspect.getdoc` does the dedenting; that is why it is used over `func.__doc__`.

- [x] **Step 5: Run the tests and watch them pass**

Run: `uv run pytest tests/test_timeline.py tests/test_compile.py -q`
Expected: PASS.

- [x] **Step 6: Mutation-test the notes path**

Break `_notes_html` to return `""` unconditionally, confirm `test_the_docstring_becomes_rendered_notes` goes red, restore. A notes assertion that survives an empty renderer is worthless.

- [x] **Step 7: Commit**

```bash
git add auditorium/timeline.py auditorium/compile.py tests/test_timeline.py tests/test_compile.py
git commit -m "feat(timeline): markers carry scene titles and speaker notes" -- auditorium/timeline.py auditorium/compile.py tests/test_timeline.py tests/test_compile.py
```

---

### Task 2: Extract the shared client runtime

`index.html` carries ~80 lines of inline module script — timeline fetch, KaTeX/hljs append hook, beat arithmetic, chrome update, rAF playback. The preview and presenter clients need all of it. Copying it three ways guarantees the three drift, and drift between surfaces is precisely the defect D2 exists to prevent.

**Files:**
- Create: `auditorium/static/client.js`
- Modify: `auditorium/static/index.html` (import from `client.js` instead of inlining)
- Test: `tests/test_present_client.py` (unchanged assertions must still pass — this task is a refactor with a behavioural gate, not a feature)

**Interfaces:**
- Produces `auditorium/static/client.js` exporting:
  - `createPlayer({ engine, onFrame })` → object with `load(timelineDict)`, `seekTo(t)`, `playTo(target)`, `pause()`, `nextBeat(from)`, `prevBeat(from)`, `beatIndex(t)`, and readable properties `beats` (ms numbers), `markers`, `duration`, `fps`, `playing`, `t`.
  - `installDecoration(engine)` — registers the KaTeX + highlight.js `onAppend` hook.
  - `connect({ onReload, onCommand, role })` → the WebSocket, with auto-reconnect and a `setStatus` callback.
- Consumes: `AuditoriumEngine` from `engine.js`.

- [x] **Step 1: Record the behavioural baseline**

Run: `uv run pytest tests/test_present_client.py -q`
Expected: PASS (12 tests). Write down the count — it is the gate this refactor must still clear.

- [x] **Step 2: Create `client.js` with the extracted logic**

Move `beatIndex`, `nextBeat`, `prevBeat`, `seekTo`, `playTo`, `loadTimeline`, the `onAppend` decoration hook and `connect()` out of `index.html` verbatim, reshaped into the exported factories above. `onFrame` is the hook the audience client uses for `updateChrome` and the preview client uses to move its scrubber — it fires after every `seek`, including every frame of playback.

Two details that must survive the move, both paid for already:

- `playTo` reads `performance.now()` for the *interactive* clock only. The renderer never calls it (it drives `window.__auditoriumShow`), so this does not reintroduce wall-clock nondeterminism into the render path.
- `load()` must set `window.__auditoriumShow = seekTo` and `window.__auditorium_ready = true`. The renderer and the exporter both gate on these; calling `AuditoriumEngine.seek` directly skips the `onFrame` hook and freezes the slide indicator, which is how "2 / 63" got burned into all 63 exported stills.

- [x] **Step 3: Rewrite `index.html`'s module script against `client.js`**

The remaining inline script should be roughly twenty lines: import, `installDecoration`, `createPlayer` with an `onFrame` that writes the indicator and the `--aud-slide-number` / `--aud-slide-total` custom properties, the keydown map, and `connect`.

- [x] **Step 4: Run the present-client suite**

Run: `uv run pytest tests/test_present_client.py -q`
Expected: PASS, same count as Step 1. Any regression here is the refactor's fault, not a flake.

- [x] **Step 5: Commit**

```bash
git add auditorium/static/client.js auditorium/static/index.html
git commit -m "refactor(client): extract the shared player out of index.html" -- auditorium/static/client.js auditorium/static/index.html
```

---

### Task 3: The preview client

The authoring surface (D8). Scrubber, time and frame readouts, single-frame stepping, loop-a-range, and hot reload that holds position.

**Files:**
- Create: `auditorium/static/preview.html`
- Modify: `auditorium/server.py` (serve `/preview`)
- Modify: `auditorium/cli.py` (add `auditorium preview`)
- Test: `tests/test_preview_client.py`

**Interfaces:**
- Consumes: `createPlayer`, `installDecoration`, `connect` from Task 2.
- Produces: route `GET /preview` → the preview HTML (always available, unlike `/presenter`); CLI command `auditorium preview <deck.py>` with the same options as `run` minus `--presenter`/`--public`.
- Exposes for tests: `window.__auditorium_preview = { t, frame, frameCount, loop: {in, out, enabled}, playing }`.

- [x] **Step 1: Write the failing tests**

Create `tests/test_preview_client.py`, modelled on `tests/test_present_client.py`'s fixture (an ephemeral uvicorn on a random port plus a real Chromium page). Tests:

```python
async def test_the_scrubber_spans_the_whole_timeline()
async def test_dragging_the_scrubber_seeks_the_stage()
async def test_the_frame_readout_matches_the_timeline_position()
async def test_step_forward_advances_exactly_one_frame()
async def test_step_backward_lands_on_the_same_state_as_seeking_there_fresh()
async def test_loop_range_wraps_playback_back_to_the_in_point()
async def test_hot_reload_holds_the_current_position()
```

`test_step_backward_lands_on_the_same_state_as_seeking_there_fresh` is the D5 guard at the client level: step forward three frames, step back one, capture `#slide-root` innerHTML and the box's computed transform; then reload the page, seek straight to that frame, capture again; assert equal. Stepping backward must go through the engine's reset-and-replay, and this is what proves it did.

`test_hot_reload_holds_the_current_position` seeks to a known `t`, evaluates the client's `reload` handler against a recompiled timeline, and asserts `AuditoriumEngine.currentTime` is still that `t` — not 0.

- [x] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_preview_client.py -q`
Expected: FAIL — 404 on `/preview`.

- [x] **Step 3: Serve `/preview` from the server**

In `auditorium/server.py`, beside the `/` route:

```python
    @app.get("/preview")
    async def preview_page() -> HTMLResponse:
        html = (STATIC_DIR / "preview.html").read_text()
        overrides = deck.theme_style_block() if deck else ""
        return HTMLResponse(html.replace("<!--AUDITORIUM_THEME_OVERRIDES-->", overrides))
```

Unlike `/presenter` this needs no mode flag: previewing is never shared, so there is no session to be in the wrong mode for.

- [x] **Step 4: Write `preview.html`**

Layout: a `#preview-stage` wrapper holding the same shell as `index.html` (`#slide-root.aud-slide-root`, the four `.aud-chrome` slots, `#slide-indicator`), CSS-scaled to fit above a fixed `#preview-bar`.

The stage must be scaled with `transform: scale()` on a wrapper of fixed 1920×1080 logical size, **not** by resizing `#slide-root`. Themes size type in `rem` against the root font size; letting the stage box shrink would reflow text and show the author a layout the renderer will never produce. A transform scales pixels, which is what a preview is for.

Control bar contents:
- play/pause button
- `<input type="range" id="scrub" min="0" max="{duration}" step="1">`
- beat ticks: a `<datalist>` is not stylable enough — draw them as absolutely-positioned 1px divs over the track at `beat.t / duration * 100%`
- time readout `mm:ss.mmm / mm:ss.mmm`
- frame readout `frame N / TOTAL`, where `TOTAL = Math.round(duration / 1000 * fps)` and `fps = tl.meta.fps || 30`
- loop in/out readout and an enable toggle

Keys: `space` play/pause, `.`/`,` step one frame forward/back, `→`/`←` next/previous beat, `i`/`o` set loop in/out to the current `t`, `l` toggle looping, `x` clear the loop, `Home`/`End` jump to 0/duration.

Playback with a loop enabled targets `loop.out`; on arrival it seeks to `loop.in` and plays again. Because that seek is backward, the engine resets and replays — the loop therefore shows exactly what a renderer would produce for that range, which is the entire point of having it.

Hot reload:

```javascript
    async function onReload() {
        const held = player.t;
        await player.load(await (await fetch('/timeline.json')).json());
        player.seekTo(Math.min(held, player.duration));
    }
```

Holding `t` — not node identity — is deliberate, and the limit is worth stating in a comment: if the edit changed what exists at that instant, the author sees the *new* scene at the *old* time, which is the useful behaviour and the only one a pure timeline can offer.

- [x] **Step 5: Add the `preview` CLI command**

In `auditorium/cli.py`, a `preview` command that mirrors `run` (same `--host/--port/--theme/--transition/--watch`) and opens `http://host:port/preview`. Factor the shared body out of `run` rather than copying it.

- [x] **Step 6: Run the tests and watch them pass**

Run: `uv run pytest tests/test_preview_client.py -q`
Expected: PASS.

- [x] **Step 7: Mutation-test the two assertions that could be vacuous**

Break the scrubber's `input` handler so it does not call `seekTo`; confirm `test_dragging_the_scrubber_seeks_the_stage` fails. Break `onReload` to seek to 0; confirm `test_hot_reload_holds_the_current_position` fails. Restore both.

- [x] **Step 8: Commit**

```bash
git add auditorium/static/preview.html auditorium/server.py auditorium/cli.py tests/test_preview_client.py
git commit -m "feat(preview): the authoring client -- scrubber, frame stepping, loop range" -- auditorium/static/preview.html auditorium/server.py auditorium/cli.py tests/test_preview_client.py
```

---

### Task 4: Shared navigation over the timeline

The presenter view's whole reason to exist is driving the audience. In 3.x that was the server's job: it held the position and pushed mutations. In 4.0 the browser holds the timeline and seeks locally, so the server relays *intent* and every surface computes the same state from it.

**Files:**
- Modify: `auditorium/server.py`
- Modify: `auditorium/static/client.js` (send/receive commands)
- Modify: `auditorium/static/index.html` (lock the audience keyboard in presenter mode)
- Test: `tests/test_server.py`, `tests/test_presenter_client.py` (created here, extended in Task 5)

**Interfaces:**
- Produces the wire protocol, complete:
  - client → server: `{"type": "hello", "role": "audience" | "presenter"}`
  - server → client: `{"type": "hello_ack", "presenter_mode": bool}`
  - presenter → server → audience: `{"type": "cmd", "cmd": "seek", "t": int}` and `{"type": "cmd", "cmd": "playTo", "from": int, "to": int}`
  - server → all: `{"type": "reload"}` (unchanged)
- Consumes: `Presentation.audience_clients` / `presenter_ws` from Stage 1.

- [x] **Step 1: Write the failing tests**

In `tests/test_server.py`, using `fastapi.testclient.TestClient`'s websocket support:

```python
def test_hello_ack_reports_presenter_mode()
def test_a_presenter_command_reaches_every_audience_client()
def test_a_command_is_not_echoed_back_to_the_presenter()
def test_an_audience_command_is_ignored()          # audience cannot drive
def test_commands_are_dropped_outside_presenter_mode()
```

`test_an_audience_command_is_ignored` matters: without it, any tab could drive every other tab, and the Readme's "audience keyboards are locked" would be a lie enforced only by the audience's own good manners.

- [x] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_server.py -q`
Expected: FAIL — no `hello_ack`, commands are drained.

- [x] **Step 3: Implement the relay**

Add to `Presentation`:

```python
    async def send_to_audience(self, message: dict) -> None:
        """Fan a command out to audience tabs only.

        Deliberately not `send()`: echoing a command back to the presenter
        that issued it would make it seek twice, and the second seek would
        be backward often enough to trigger a full reset mid-talk.
        """
        data = json.dumps(message)
        for ws in list(self.audience_clients):
            try:
                await ws.send_text(data)
            except Exception:
                self.audience_clients.remove(ws)
```

In both `_handle_shared_session` and `_handle_independent_session`, send `hello_ack` immediately after accepting the role. In the shared-session receive loop, replace the drain with: parse the message; if it is a `cmd` **and** this socket is the presenter, `await pres.send_to_audience(msg)`; otherwise ignore it. Malformed JSON is ignored, not fatal — a bad frame from one tab must not close the presentation.

- [x] **Step 4: Teach the client to send and obey commands**

`connect()` gains an `onCommand` callback and a `send(cmd)` method on the returned socket wrapper. In `index.html`, the audience:
- stores `presenterMode` from `hello_ack`;
- ignores keydown entirely while `presenterMode` is true (the lock);
- on `cmd`, calls `player.seekTo(t)` or `player.playTo(to)` accordingly.

- [x] **Step 5: Run the tests and watch them pass**

Run: `uv run pytest tests/test_server.py -q`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add auditorium/server.py auditorium/static/client.js auditorium/static/index.html tests/test_server.py
git commit -m "feat(server): relay presenter commands instead of positions" -- auditorium/server.py auditorium/static/client.js auditorium/static/index.html tests/test_server.py
```

---

### Task 5: Rebuild the presenter view

`static/presenter.html` is untouched 3.x: it switches on `mutation`, `clear`, `slide`, `notes`, `next_preview` and acks every mutation. Not one of those messages exists in 4.0, so the page renders nothing. It is replaced wholesale — this is a rewrite, not a repair.

**Files:**
- Rewrite: `auditorium/static/presenter.html`
- Modify: `auditorium/static/theme.css` **only if** presenter-specific rules are missing (check first — the 3.x layout rules for `#presenter-container`, `#slide-pane`, `#info-pane` may already be there; another agent is editing this file, so touch only rules you add)
- Test: `tests/test_presenter_client.py`

**Interfaces:**
- Consumes: `createPlayer`/`installDecoration`/`connect` (Task 2), the `cmd` protocol (Task 4), `timeline.markers` (Task 1).
- Produces: nothing other tasks consume.

- [x] **Step 1: Write the failing tests**

In `tests/test_presenter_client.py`, with a server started `presenter_mode=True` and two pages (`/presenter` and `/`):

```python
async def test_the_presenter_mirrors_the_stage()
async def test_notes_come_from_the_current_scene_marker()
async def test_the_next_preview_names_the_following_scene()
async def test_the_last_scene_says_it_is_last()
async def test_advancing_the_presenter_advances_the_audience()
async def test_the_audience_keyboard_does_not_move_the_presenter()
async def test_the_timer_starts_on_the_first_advance()
async def test_presenter_route_is_403_without_presenter_mode()
```

`test_advancing_the_presenter_advances_the_audience` is the one that would have caught the shipped bug: open both pages, press space on the presenter, assert the *audience* page's `AuditoriumEngine.currentTime` moved. Asserting only that the presenter moved is the proxy signal that let a broken presenter ship.

- [x] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_presenter_client.py -q`
Expected: FAIL — the current page renders an empty mirror and never seeks.

- [x] **Step 3: Rewrite `presenter.html`**

Structure stays as it was (it is a good layout): left pane a scaled stage mirror, right pane notes + next preview + footer with timer and indicator. What changes is everything below the markup:

- Import `engine.js` and `client.js`; build a player exactly as the audience does. The mirror is a real engine over the real timeline — not a copy of the audience's DOM. Two engines seeking the same timeline agree by construction (D2); a DOM mirror would be a second path that can disagree.
- Scale the stage pane with `transform: scale()` on a fixed 1920×1080 wrapper, for the same reason as the preview.
- `onFrame` updates: indicator (`beatIndex + 1 / beats + 1`), the notes pane from `markerAt(t)`, and the next-preview pane from `markerAfter(t)`.
- `markerAt(t)` = the last marker with `m.t <= t`; `markerAfter(t)` = the first with `m.t > t`, or `null` → render "Last scene".
- Next-preview excerpt: the next marker's `notes_html` with tags stripped, truncated to 200 characters. Strip via `textContent` of a detached element, never a regex — notes are author-authored HTML.
- Keydown mirrors the audience's map (space/→ next beat, ← previous, `r` restart, `End`), and after acting locally sends the matching `cmd` so the audience follows.
- Timer starts on the first advance, not on load, so a presenter who opens the deck early does not start the clock.

- [x] **Step 4: Run the tests and watch them pass**

Run: `uv run pytest tests/test_presenter_client.py -q`
Expected: PASS.

- [x] **Step 5: Watch it, do not infer it**

Run `uv run auditorium run examples/demo_deck.py --presenter --no-open`, open both tabs in a real browser, advance three times from the presenter, and confirm with your own eyes: the audience follows, the notes match the scene, the next preview names the right one. Screenshot both. The suite can prove the wiring; only looking proves the feature.

- [x] **Step 6: Commit**

```bash
git add auditorium/static/presenter.html tests/test_presenter_client.py
git commit -m "feat(presenter): rebuild the presenter view over the timeline" -- auditorium/static/presenter.html tests/test_presenter_client.py
```

---

### Task 6: Retire the beta warnings

The `b1` suffix, the three Readme warnings, and the CHANGELOG note all exist because the presenter was broken. Once Task 5 lands they are false, and a false warning costs more than none.

**Files:**
- Modify: `Readme.md` (lines ~45, ~102-103, ~154-168)
- Modify: `CHANGELOG.md`
- Modify: `CLAUDE.md` (the `presenter.html` and `cli.py` bullets under "Key modules"; add `preview.html` and `client.js`)
- Modify: `docs/design/2026-08-26-scene-engine.md` (status header, delivery-order note)

- [x] **Step 1: Remove every "broken in 4.0 beta" claim from `Readme.md`**

Grep first — `grep -n "beta\|broken\|being rebuilt" Readme.md` — and fix every hit, not the three remembered ones. Document `auditorium preview` in the feature table and give it a short section next to Presenter Mode.

- [x] **Step 2: Update `CHANGELOG.md`** with the preview client, the presenter rebuild, timeline markers, and the `cmd` protocol.

- [x] **Step 3: Update the spec's status header** to `stage-1-2-3-implemented` and replace the "Stages 2-4 are not started" note in Delivery order with what actually landed, including the two decisions this stage made that the spec did not anticipate: markers as a timeline member, and shared navigation as broadcast intent rather than broadcast position.

- [x] **Step 4: Commit**

```bash
git add Readme.md CHANGELOG.md CLAUDE.md docs/design/2026-08-26-scene-engine.md
git commit -m "docs: preview client documented, presenter warnings retired" -- Readme.md CHANGELOG.md CLAUDE.md docs/design/2026-08-26-scene-engine.md
```

---

### Task 7: Full-suite gate

- [x] **Step 1: Run the whole suite as its own tool call, unpiped**

Run: `uv run pytest -q`
Expected: every test passes. Do not pipe it into `tail` and do not chain it with `&&` — a pipe hands the shell `tail`'s exit code, which turns a red gate green.

- [x] **Step 2: Confirm the render path still works end to end**

Run: `uv run auditorium render examples/demo_deck.py -o /tmp/stage2.mp4 --fps 10 --size 720p --to 60`, then `ffprobe` the artifact for a packet count of 60. Stage 2 touched `index.html`, which the renderer drives; a green unit suite does not prove the video still renders.

- [x] **Step 3: Journal and release the lock**
