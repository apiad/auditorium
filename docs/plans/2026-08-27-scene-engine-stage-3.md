# Auditorium 4.0 Scene Engine — Stage 3 (Renderer) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a compiled timeline into an mp4 by stepping frames deterministically, and un-break `auditorium export` by moving it onto the same seek-based drive path.

**Architecture:** The renderer is a fourth consumer of `seek(t)`, alongside present and preview. For each frame it seeks to that frame's timeline position, screenshots, and pipes the PNG to ffmpeg's stdin. Which timeline position each frame maps to is decided by a pure function (`render_schedule`) that inserts beat dwells, so the frame plan is unit-testable without a browser. Frame ranges are addressable via `--from`/`--to`, which makes parallel rendering a shell-level fan-out.

**Tech Stack:** Python 3.12+, Playwright (Chromium 1234), ffmpeg (system, `/usr/bin/ffmpeg`), pytest.

**Spec:** `docs/design/2026-08-26-scene-engine.md` (see D9 and the "The renderer" component)

**Predecessor:** `docs/plans/2026-08-27-scene-engine-stage-1.md` — complete, `1!4.0.0a1`, 67 tests green.

## Global Constraints

- **Committing in a shared checkout.** Concurrent agents share one working tree and index. Every commit step uses:
  ```bash
  git add <explicit paths> && git commit -m "message" -- <the same explicit paths>
  ```
  Both halves required: `git commit -- <path>` alone fails on a **new** file, and `-m` must precede `--`. Never `git add -A`, `git add .`, `git add -u`, `--amend`, `git stash`, or `git checkout`/`restore` on a path your task did not create.
- **PDF export is gone as of 2026-08-27** (`_build_pdf` deleted, CLI rejects `-f pdf` with a rationale). Do not reintroduce it. A timeline has no canonical instant to print; `png` and `html` survive because both are total functions of the timeline. See `Readme.md` → "Why there is no PDF export".
- **`_build_html` and `_inline_katex_fonts` in `exporter.py` are OFF LIMITS.** `_inline_katex_fonts` is shared with the HTML bundle, not PDF-only. Stage 3 touches only `export_deck`'s drive path. Before editing, run `git diff auditorium/exporter.py` and leave every hunk you did not write.
- All times in the timeline are integer milliseconds. Frame indices are integers; `fps` is an integer.
- Rendering must be deterministic: same timeline, same frames, byte-identical output. Nothing in the render path may read a wall clock.
- Playwright and ffmpeg stay optional — importing `auditorium.render` must not require them; only calling the render entry point does.
- English for code, comments, identifiers, commit messages, and test names.

---

### Task 1: The frame schedule

A pure function, so the hard part is testable without a browser or ffmpeg.

**Files:**
- Create: `auditorium/render.py`
- Create: `tests/test_render_schedule.py`

**Interfaces:**
- Consumes: `auditorium.timeline.Timeline`.
- Produces: `render_schedule(timeline: Timeline, fps: int) -> list[int]` — one timeline-time (ms) per output frame, in order; `frame_count(timeline, fps) -> int`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render_schedule.py`:

```python
from auditorium.render import frame_count, render_schedule
from auditorium.timeline import Beat, Op, Timeline, Track


def tl_of(duration_ms, beats=()):
    tl = Timeline(meta={"title": "T"})
    tl.ops.append(Op(t=0, action="append", node="n1"))
    tl.tracks.append(
        Track(node="n1", prop="opacity", from_=0, to=1, start=0, end=duration_ms)
    )
    for t, hold in beats:
        tl.beats.append(Beat(t=t, hold_ms=hold))
    return tl


def test_a_one_second_timeline_at_30fps_is_thirty_frames():
    assert frame_count(tl_of(1000), 30) == 30


def test_frames_are_evenly_spaced_in_timeline_time():
    sched = render_schedule(tl_of(1000), 10)
    assert sched == [0, 100, 200, 300, 400, 500, 600, 700, 800, 900]


def test_a_beat_with_zero_hold_adds_no_frames():
    assert frame_count(tl_of(1000, beats=[(500, 0)]), 10) == 10


def test_a_beat_dwell_repeats_that_timeline_position():
    sched = render_schedule(tl_of(1000, beats=[(500, 200)]), 10)
    # 2 extra frames at t=500 (200ms at 10fps), inserted where the beat sits.
    assert sched.count(500) == 3
    assert len(sched) == 12


def test_dwell_frames_are_contiguous_and_in_place():
    sched = render_schedule(tl_of(1000, beats=[(500, 200)]), 10)
    first = sched.index(500)
    assert sched[first : first + 3] == [500, 500, 500]
    assert sched[first + 3] == 600


def test_multiple_beats_each_dwell():
    tl = tl_of(1000, beats=[(300, 100), (700, 100)])
    assert frame_count(tl, 10) == 12


def test_schedule_is_monotonic_non_decreasing():
    """The renderer only ever seeks forward; a decreasing schedule would make
    every frame after it pay a full reset-and-replay."""
    sched = render_schedule(tl_of(2000, beats=[(500, 300), (1500, 200)]), 24)
    assert all(b >= a for a, b in zip(sched, sched[1:]))


def test_an_empty_timeline_yields_no_frames():
    assert render_schedule(Timeline(), 30) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render_schedule.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'auditorium.render'`

- [ ] **Step 3: Write the implementation**

Create `auditorium/render.py`:

```python
"""Frame-stepped rendering. The fourth consumer of seek(t).

Nothing here reads a wall clock. Which timeline position each output frame
shows is decided by render_schedule() -- a pure function -- so the frame plan
can be tested without a browser, and so two renders of the same timeline
produce the same frames by construction rather than by luck.
"""
from __future__ import annotations

from auditorium.timeline import Timeline


def render_schedule(timeline: Timeline, fps: int) -> list[int]:
    """Return one timeline time (ms) per output frame, in order.

    Beats have no intrinsic length in the timeline, but a rendered video has
    to dwell on them or a slide deck blasts past every reveal. Each beat's
    hold_ms becomes repeated frames at that same timeline position, inserted
    where the beat sits.
    """
    duration = timeline.duration_ms
    if duration <= 0 and not timeline.beats:
        return []

    step_ms = 1000 / fps
    holds = {b.t: b.hold_ms for b in timeline.beats if b.hold_ms > 0}

    schedule: list[int] = []
    emitted_holds: set[int] = set()
    n = int(duration * fps / 1000)
    for i in range(n):
        t = int(i * step_ms)
        schedule.append(t)
        # Dwell on any beat this frame has just reached or passed.
        for beat_t, hold_ms in sorted(holds.items()):
            if beat_t in emitted_holds:
                continue
            if t >= beat_t:
                extra = int(hold_ms * fps / 1000)
                schedule.extend([t] * extra)
                emitted_holds.add(beat_t)
    return schedule


def frame_count(timeline: Timeline, fps: int) -> int:
    """Number of frames a render of this timeline will produce."""
    return len(render_schedule(timeline, fps))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render_schedule.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add auditorium/render.py tests/test_render_schedule.py && git commit -m "feat(render): pure frame schedule with beat dwells" -- auditorium/render.py tests/test_render_schedule.py
```

---

### Task 2: Frame capture to PNG sequence

Get frames out of a browser before involving ffmpeg, so a failure here is unambiguous.

**Files:**
- Modify: `auditorium/render.py`
- Create: `tests/test_render_frames.py`

**Interfaces:**
- Consumes: Task 1's `render_schedule`; `auditorium.compile.compile_deck`; `auditorium.server.create_app`.
- Produces: `async render_frames(deck, out_dir: Path, *, fps: int = 30, size: tuple[int, int] = (1920, 1080), start_frame: int = 0, end_frame: int | None = None, port: int = 0) -> int` — writes `frame-%06d.png`, returns the count written.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render_frames.py`:

```python
import hashlib
from pathlib import Path

import pytest

from auditorium.deck import Deck
from auditorium.render import render_frames


def _deck():
    deck = Deck("Render")

    @deck.scene
    async def one(s):
        h = await s.show("<p style='font-size:80px'>HELLO</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)
        await s.play(h.animate.move_to(200, 0), run_time=0.5)

    return deck


def _digests(d: Path):
    return [hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.glob("*.png"))]


async def test_renders_the_expected_number_of_frames(tmp_path):
    n = await render_frames(_deck(), tmp_path, fps=10, size=(320, 240))
    assert n == 10
    assert len(list(tmp_path.glob("*.png"))) == 10


async def test_frames_are_not_all_identical(tmp_path):
    """Guards the whole point: if seek() were a no-op every frame would match
    and a frame-count assertion alone would still pass."""
    await render_frames(_deck(), tmp_path, fps=10, size=(320, 240))
    assert len(set(_digests(tmp_path))) > 1


async def test_two_renders_are_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    await render_frames(_deck(), a, fps=10, size=(320, 240))
    await render_frames(_deck(), b, fps=10, size=(320, 240))
    assert _digests(a) == _digests(b)


async def test_frame_zero_is_not_blank(tmp_path):
    """Without a fonts.ready gate exactly one frame is wrong, and it is this one.

    Compared against an empty deck's frame: a solid-colour PNG compresses to
    almost nothing, so a frame with rendered text is several times larger.
    Asserting merely that frame 0 is non-empty would pass on a blank image.
    """
    empty = Deck("Empty")

    @empty.scene
    async def nothing(s):
        await s.wait(1.0)

    blank_dir = tmp_path / "blank"
    real_dir = tmp_path / "real"
    blank_dir.mkdir()
    real_dir.mkdir()
    await render_frames(empty, blank_dir, fps=10, size=(320, 240))
    await render_frames(_deck(), real_dir, fps=10, size=(320, 240))

    blank_size = sorted(blank_dir.glob("*.png"))[0].stat().st_size
    first_size = sorted(real_dir.glob("*.png"))[0].stat().st_size
    assert first_size > blank_size * 2, (
        f"frame 0 ({first_size}B) is close to blank ({blank_size}B) — "
        "content had not rendered when it was captured"
    )


async def test_a_frame_range_renders_only_that_range(tmp_path):
    n = await render_frames(_deck(), tmp_path, fps=10, size=(320, 240),
                            start_frame=3, end_frame=6)
    assert n == 3
    names = sorted(p.name for p in tmp_path.glob("*.png"))
    assert names == ["frame-000003.png", "frame-000004.png", "frame-000005.png"]


async def test_a_range_matches_the_same_frames_of_a_full_render(tmp_path):
    """The claim that makes parallel rendering safe: a worker starting at frame
    N produces exactly what a sequential render produces at frame N."""
    full, part = tmp_path / "full", tmp_path / "part"
    full.mkdir()
    part.mkdir()
    await render_frames(_deck(), full, fps=10, size=(320, 240))
    await render_frames(_deck(), part, fps=10, size=(320, 240),
                        start_frame=4, end_frame=7)
    full_d = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in full.glob("*.png")}
    part_d = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in part.glob("*.png")}
    assert part_d
    for name, digest in part_d.items():
        assert full_d[name] == digest, f"{name} differs between full and ranged render"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render_frames.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_frames'`

- [ ] **Step 3: Write the implementation**

Append to `auditorium/render.py`:

```python
import asyncio
import threading
from pathlib import Path

FRAME_NAME = "frame-{:06d}.png"


async def render_frames(
    deck,
    out_dir: Path,
    *,
    fps: int = 30,
    size: tuple[int, int] = (1920, 1080),
    start_frame: int = 0,
    end_frame: int | None = None,
    port: int = 0,
) -> int:
    """Render frames to PNGs in out_dir. Returns how many were written.

    A worker rendering [start_frame, end_frame) still replays the schedule
    from frame 0 without screenshotting, because seek() is only correct
    forward -- jumping straight to a mid-timeline position would reach a state
    a sequential render never passes through.
    """
    import uvicorn
    from playwright.async_api import async_playwright

    from auditorium.compile import compile_deck
    from auditorium.server import create_app

    timeline = await compile_deck(deck)
    schedule = render_schedule(timeline, fps)
    stop = len(schedule) if end_frame is None else min(end_frame, len(schedule))

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    config = uvicorn.Config(create_app(deck), host="127.0.0.1", port=port,
                            log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = 10.0
    while not server.started:
        await asyncio.sleep(0.05)
        deadline -= 0.05
        if deadline <= 0:
            server.should_exit = True
            raise RuntimeError("uvicorn did not start within 10s")
    bound = server.servers[0].sockets[0].getsockname()[1]

    written = 0
    try:
        width, height = size
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            page = await context.new_page()
            await page.goto(f"http://127.0.0.1:{bound}/")
            await page.wait_for_function(
                "() => window.__auditorium_ready === true", timeout=30000
            )
            # Frame 0 renders blank without this: webfonts and images resolve
            # after the timeline loads, and nothing else waits for them.
            await page.evaluate(
                """async () => {
                    await document.fonts.ready;
                    const imgs = [...document.images].map(
                        (i) => (i.decode ? i.decode().catch(() => {}) : null)
                    );
                    await Promise.all(imgs);
                }"""
            )

            for index in range(stop):
                t = schedule[index]
                await page.evaluate("(t) => window.AuditoriumEngine.seek(t)", t)
                if index < start_frame:
                    continue
                await page.screenshot(
                    path=str(out_dir / FRAME_NAME.format(index)),
                    animations="disabled",
                )
                written += 1
            await context.close()
            await browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)

    return written
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render_frames.py -v`
Expected: 6 passed

- [ ] **Step 5: Prove the determinism test can fail**

Temporarily make `seek` non-deterministic by adding a wall-clock read in `render_frames`'s loop — change the seek line to:

```python
                await page.evaluate("(t) => window.AuditoriumEngine.seek(t + (Date.now() % 3))", t)
```

Run: `uv run pytest tests/test_render_frames.py::test_two_renders_are_byte_identical -v`
Expected: FAIL. Restore the original line and confirm it passes. Do not commit the broken version. Report the failure output.

- [ ] **Step 6: Commit**

```bash
git add auditorium/render.py tests/test_render_frames.py && git commit -m "feat(render): deterministic frame capture with fonts gate and frame ranges" -- auditorium/render.py tests/test_render_frames.py
```

---

### Task 3: Encode to mp4

**Files:**
- Modify: `auditorium/render.py`
- Create: `tests/test_render_encode.py`

**Interfaces:**
- Consumes: Task 2's `render_frames`.
- Produces: `async render_video(deck, output: Path, *, fps=30, size=(1920,1080), audio: Path | None = None, fmt: str = "mp4", start_frame: int = 0, end_frame: int | None = None) -> Path`; `SIZE_PRESETS: dict[str, tuple[int, int]]`; `parse_size(value: str) -> tuple[int, int]`. The frame-range arguments are declared here, not bolted on in Task 4, so the CLI has a signature to call.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render_encode.py`:

```python
import shutil
import subprocess
from pathlib import Path

import pytest

from auditorium.deck import Deck
from auditorium.render import parse_size, render_video

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


def _deck():
    deck = Deck("Video")

    @deck.scene
    async def one(s):
        h = await s.show("<p style='font-size:80px'>HELLO</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)

    return deck


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_name,width,height,nb_read_packets",
         "-count_packets", "-select_streams", "v:0", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def test_size_presets_resolve():
    assert parse_size("1920x1080") == (1920, 1080)
    assert parse_size("vertical") == (1080, 1920)
    assert parse_size("square") == (1080, 1080)


def test_an_unknown_size_is_rejected():
    with pytest.raises(ValueError):
        parse_size("enormous")


async def test_produces_a_playable_mp4(tmp_path):
    out = await render_video(_deck(), tmp_path / "o.mp4", fps=10, size=(320, 240))
    assert out.exists() and out.stat().st_size > 0
    probe = _probe(out)
    assert "h264" in probe
    assert "320,240" in probe


async def test_the_video_has_the_scheduled_frame_count(tmp_path):
    """Asserts on the encoded artifact, not on how many PNGs we wrote."""
    out = await render_video(_deck(), tmp_path / "o.mp4", fps=10, size=(320, 240))
    assert _probe(out).split(",")[-1] == "5"


async def test_two_renders_produce_identical_video_bytes(tmp_path):
    a = await render_video(_deck(), tmp_path / "a.mp4", fps=10, size=(320, 240))
    b = await render_video(_deck(), tmp_path / "b.mp4", fps=10, size=(320, 240))
    assert a.read_bytes() == b.read_bytes()


async def test_png_sequence_format_leaves_frames_on_disk(tmp_path):
    out = await render_video(_deck(), tmp_path / "seq", fps=10, size=(320, 240),
                             fmt="png-sequence")
    assert len(list(Path(out).glob("*.png"))) == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render_encode.py -v`
Expected: FAIL with `ImportError: cannot import name 'parse_size'`

- [ ] **Step 3: Write the implementation**

Append to `auditorium/render.py`:

```python
import shutil
import subprocess
import tempfile

SIZE_PRESETS = {
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "vertical": (1080, 1920),
    "square": (1080, 1080),
}


def parse_size(value: str) -> tuple[int, int]:
    """Resolve a named preset or a WIDTHxHEIGHT string."""
    if value in SIZE_PRESETS:
        return SIZE_PRESETS[value]
    parts = value.lower().split("x")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(
            f"invalid size {value!r}; use WIDTHxHEIGHT or one of "
            f"{', '.join(sorted(SIZE_PRESETS))}"
        )
    return int(parts[0]), int(parts[1])


async def render_video(
    deck,
    output: Path,
    *,
    fps: int = 30,
    size: tuple[int, int] = (1920, 1080),
    audio: Path | None = None,
    fmt: str = "mp4",
    start_frame: int = 0,
    end_frame: int | None = None,
) -> Path:
    """Render a deck to a video file (or a PNG sequence directory)."""
    output = Path(output)
    frame_range = {"start_frame": start_frame, "end_frame": end_frame}

    if fmt == "png-sequence":
        await render_frames(deck, output, fps=fps, size=size, **frame_range)
        return output

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to encode video; install it or use --format png-sequence")

    with tempfile.TemporaryDirectory(prefix="auditorium-render-") as tmp:
        frames = Path(tmp)
        await render_frames(deck, frames, fps=fps, size=size, **frame_range)
        # A ranged render's files start at frame-%06d of the RANGE start, so
        # ffmpeg needs to be told where the sequence begins or it finds nothing.
        first_index = start_frame

        codec = ["-c:v", "libx264", "-pix_fmt", "yuv420p"] if fmt == "mp4" else ["-c:v", "libvpx-vp9"]
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-start_number", str(first_index),
            "-i", str(frames / "frame-%06d.png"),
        ]
        if audio is not None:
            cmd += ["-i", str(audio), "-c:a", "aac", "-shortest"]
        cmd += codec
        # Strip metadata so two renders of the same timeline are byte-identical;
        # ffmpeg otherwise stamps an encoder string and creation time.
        cmd += ["-map_metadata", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact"]
        cmd += [str(output)]

        output.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed (rc={result.returncode}):\n{result.stderr[-2000:]}")

    return output
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render_encode.py -v`
Expected: 6 passed. If `test_two_renders_produce_identical_video_bytes` fails, ffmpeg is still stamping something — find it with `ffprobe -show_format` on both files and extend the bitexact flags rather than deleting the test.

- [ ] **Step 5: Commit**

```bash
git add auditorium/render.py tests/test_render_encode.py && git commit -m "feat(render): encode frames to mp4 with bit-exact output" -- auditorium/render.py tests/test_render_encode.py
```

---

### Task 4: CLI — `auditorium render` replaces `record`

**Files:**
- Modify: `auditorium/cli.py`
- Delete: `auditorium/recorder.py`
- Create: `tests/test_render_cli.py`

**Interfaces:**
- Consumes: `auditorium.render.{render_video, parse_size}`.
- Produces: `auditorium render <deck.py> [-o OUT] [--fps N] [--size S] [--from T] [--to T] [--format F] [--audio PATH]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_render_cli.py`:

```python
import shutil

import pytest
from typer.testing import CliRunner

from auditorium.cli import app

runner = CliRunner()


def test_render_command_exists_and_documents_itself():
    result = runner.invoke(app, ["render", "--help"])
    assert result.exit_code == 0
    for flag in ["--fps", "--size", "--format", "--audio"]:
        assert flag in result.stdout


def test_record_is_gone():
    """record produced nondeterministic screen capture; render replaces it."""
    result = runner.invoke(app, ["record", "--help"])
    assert result.exit_code != 0


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_render_writes_a_file(tmp_path):
    out = tmp_path / "out.mp4"
    result = runner.invoke(app, [
        "render", "examples/demo_deck.py", "-o", str(out),
        "--fps", "5", "--size", "320x240", "--to", "10",
    ])
    assert result.exit_code == 0, result.stdout
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render_cli.py -v`
Expected: FAIL — no `render` command, and `record` still exists.

- [ ] **Step 3: Replace the command**

In `auditorium/cli.py`, delete the entire `record` command (starting at the `@app.command()` above `def record(`) and the `from auditorium.recorder import record as do_record` import, then add:

```python
@app.command()
def render(
    deck_path: Path = typer.Argument(..., help="Path to the deck file"),
    output: Path = typer.Option(Path("out.mp4"), "-o", "--output", help="Output file"),
    fps: int = typer.Option(30, "--fps", help="Frames per second"),
    size: str = typer.Option("1080p", "--size", help="WIDTHxHEIGHT or a preset: 1080p, 720p, vertical, square"),
    fmt: str = typer.Option("mp4", "--format", help="mp4, webm, or png-sequence"),
    audio: Path | None = typer.Option(None, "--audio", help="Audio bed mixed into the render"),
    from_frame: int = typer.Option(0, "--from", help="First frame to render"),
    to_frame: int | None = typer.Option(None, "--to", help="Stop before this frame"),
    theme: list[str] | None = typer.Option(None, "--theme"),
    transition: str | None = typer.Option(None, "--transition"),
) -> None:
    """Render a deck to video by stepping frames deterministically."""
    from auditorium.render import parse_size, render_video

    deck = _load_deck(deck_path)
    _apply_theme_override(deck, theme, transition)
    try:
        width, height = parse_size(size)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    asyncio.run(render_video(
        deck, output, fps=fps, size=(width, height), audio=audio, fmt=fmt,
        start_frame=from_frame, end_frame=to_frame,
    ))
    console.print(f"[green]✓[/] Rendered to [bold]{output}[/]")
```

Then thread `start_frame`/`end_frame` through `render_video` to `render_frames` (add the two keyword arguments to `render_video`'s signature and pass them down).

Delete `auditorium/recorder.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render_cli.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add auditorium/cli.py tests/test_render_cli.py && git rm auditorium/recorder.py && git commit -m "feat(cli): auditorium render replaces record" -- auditorium/cli.py tests/test_render_cli.py auditorium/recorder.py
```

---

### Task 5: Un-break `auditorium export`

`export` currently hangs — it drives the deck with `?instant_sleep=1&auto_step=0` query parameters the server no longer parses, then waits forever on `window.__auditorium_slide_complete`, which the new client never sets. Verified: `TimeoutError: Page.wait_for_function: Timeout 120000ms exceeded`, no output produced.

**Files:**
- Modify: `auditorium/exporter.py` — **only** the drive path inside `export_deck` (roughly lines 90–155)
- Create: `tests/test_export.py`

**SCOPE FENCE:** `_build_html`, `_inline_katex_fonts`, and `_capture` are OFF LIMITS. `_build_pdf` no longer exists — PDF export was removed on 2026-08-27; do not reintroduce it. Run `git diff auditorium/exporter.py` before you start and preserve every hunk you did not write.

**Interfaces:**
- Consumes: `auditorium.compile.compile_deck`, the client's `window.AuditoriumEngine`.
- Produces: unchanged public signature for `export_deck`; internally it seeks to each beat instead of driving slides.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_export.py`:

```python
import asyncio
from pathlib import Path

import pytest

from auditorium.exporter import export_deck

DECK_SRC = '''
from auditorium import Deck

deck = Deck("Export")

@deck.scene
async def alpha(s):
    await s.show("<p>ALPHA</p>")

@deck.scene
async def bravo(s):
    await s.show("<p>BRAVO</p>")
'''


@pytest.fixture
def deck_file(tmp_path):
    """export_deck takes a PATH, not a Deck: it loads the module itself."""
    path = tmp_path / "d.py"
    path.write_text(DECK_SRC)
    return path


async def test_png_export_writes_one_image_per_beat(deck_file, tmp_path):
    out = tmp_path / "png"
    await export_deck(deck_file, out, "png", "320x240", False, 0)
    pngs = sorted(out.glob("*.png"))
    assert len(pngs) >= 2
    assert all(p.stat().st_size > 0 for p in pngs)


async def test_export_completes_without_hanging(deck_file, tmp_path):
    """The regression this task fixes: export waited forever on
    window.__auditorium_slide_complete, which the new client never sets.
    Measured before the fix: TimeoutError after 120s, no output produced."""
    out = tmp_path / "png2"
    await asyncio.wait_for(
        export_deck(deck_file, out, "png", "320x240", False, 0), timeout=90
    )
```

Confirm the import path first — if `from auditorium import Deck` does not work, use `from auditorium.deck import Deck` in `DECK_SRC` and say so in your report.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_export.py -v`
Expected: FAIL by timeout (the current drive path hangs).

- [ ] **Step 3: Replace the drive path**

Inside `export_deck`, replace the per-slide URL/wait logic with: load the page once, wait for `window.__auditorium_ready`, read the beat list from `window.AuditoriumEngine._tl.beats`, then for each beat seek to it and capture. Keep the `slide_doms` structure that `_build_html` consumes — that function must not change:

```python
        await page.goto(f"http://127.0.0.1:{port}/", wait_until="load")
        await page.wait_for_function("() => window.__auditorium_ready === true", timeout=30000)
        await page.evaluate("async () => { await document.fonts.ready; }")

        beat_times = await page.evaluate(
            "() => window.AuditoriumEngine._tl.beats.map(b => b.t)"
        )
        # A deck with no beats is still one capturable frame: its end state.
        stops = beat_times or [await page.evaluate("() => window.AuditoriumEngine._tl.meta.duration_ms")]

        for i, t in enumerate(stops):
            await page.evaluate("(t) => window.AuditoriumEngine.seek(t)", t)
            slide_doms.append({
                "html": await page.evaluate("() => document.getElementById('slide-root').innerHTML"),
                "classes": await page.evaluate("() => document.getElementById('slide-root').className"),
            })
            await _capture(page, fmt, output, slide_doms, i, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_export.py -v`
Expected: 2 passed

- [ ] **Step 5: Verify the real command, not just the test**

Run: `uv run auditorium export examples/demo_deck.py -f png -o /tmp/stage3-png/`
Expected: completes and writes one PNG per beat. Open several and confirm scenes are distinct and not piled on top of each other. Report the count.

- [ ] **Step 6: Commit**

```bash
git add auditorium/exporter.py tests/test_export.py && git commit -m "fix(export): drive by seeking to beats instead of dead query params" -- auditorium/exporter.py tests/test_export.py
```

---

### Task 6: Audio bed

**Files:**
- Modify: `auditorium/deck.py`, `auditorium/compile.py`, `auditorium/render.py`
- Create: `tests/test_render_audio.py`

**Interfaces:**
- Consumes: Task 3's `render_video`.
- Produces: `Deck.audio(path: str | Path, *, at: float = 0.0)`; the timeline's `audio` list is populated by `compile_deck`; `render_video` mixes it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render_audio.py`:

```python
import shutil
import subprocess

import pytest

from auditorium.compile import compile_deck
from auditorium.deck import Deck
from auditorium.render import render_video

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


@pytest.fixture
def tone(tmp_path):
    """A 3-second sine wave, generated rather than committed as a fixture."""
    path = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         str(path)],
        capture_output=True, check=True,
    )
    return path


def _deck(tone=None):
    deck = Deck("Audio")
    if tone is not None:
        deck.audio(tone)

    @deck.scene
    async def one(s):
        h = await s.show("<p>x</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)

    return deck


async def test_declared_audio_reaches_the_timeline(tone):
    tl = await compile_deck(_deck(tone))
    assert tl.audio and tl.audio[0]["at"] == 0.0


async def test_rendered_video_has_an_audio_stream(tmp_path, tone):
    out = await render_video(_deck(tone), tmp_path / "o.mp4", fps=10, size=(320, 240))
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True,
    )
    assert "aac" in probe.stdout


async def test_audio_is_truncated_to_the_video_length(tmp_path, tone):
    """The tone is 3s; the timeline is 0.5s. -shortest must win."""
    out = await render_video(_deck(tone), tmp_path / "o.mp4", fps=10, size=(320, 240))
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(out)],
        capture_output=True, text=True,
    )
    assert float(dur.stdout.strip()) < 1.5


async def test_a_deck_without_audio_still_renders(tmp_path):
    out = await render_video(_deck(), tmp_path / "o.mp4", fps=10, size=(320, 240))
    assert out.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render_audio.py -v`
Expected: FAIL with `AttributeError: 'Deck' object has no attribute 'audio'`

- [ ] **Step 3: Implement**

In `auditorium/deck.py`, add to `Deck.__init__`: `self._audio: list[dict] = []`, and the method:

```python
    def audio(self, path: str | Path, *, at: float = 0.0) -> None:
        """Declare an audio bed mixed in at render time.

        Not part of the timeline's visual state: seek() ignores it entirely,
        and interactive playback is silent. Only rendering consumes it.
        """
        self._audio.append({"src": str(path), "at": at})
```

In `auditorium/compile.py`, after building `tl`, add `tl.audio = list(getattr(deck, "_audio", []))`.

In `render_video`, take the audio from the compiled timeline when the `audio=` argument is not given, so a deck-declared bed is used automatically.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render_audio.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add auditorium/deck.py auditorium/compile.py auditorium/render.py tests/test_render_audio.py && git commit -m "feat(render): audio bed mixed at encode time" -- auditorium/deck.py auditorium/compile.py auditorium/render.py tests/test_render_audio.py
```

---

### Task 7: Verification and release readiness

**Files:**
- Modify: `pyproject.toml`, `auditorium/cli.py`, `CHANGELOG.md`, `Readme.md`, `CLAUDE.md`

- [ ] **Step 1: Render the demo deck end to end**

Run: `uv run auditorium render examples/demo_deck.py -o /tmp/demo.mp4 --fps 30 --size 720p`
Then: `ffprobe -v error -show_entries format=duration,size -of default=nw=1 /tmp/demo.mp4`
Expected: a non-empty mp4 whose duration matches `duration_ms + sum(beat holds)`. Watch it. Confirm slides advance, are not piled on top of each other, and animations move.

- [ ] **Step 2: Prove the parallel claim on a real deck**

```bash
uv run auditorium render examples/demo_deck.py -o /tmp/a.mp4 --fps 10 --size 320x240 --to 40
uv run auditorium render examples/demo_deck.py -o /tmp/b.mp4 --fps 10 --size 320x240 --from 0 --to 20
uv run auditorium render examples/demo_deck.py -o /tmp/c.mp4 --fps 10 --size 320x240 --from 20 --to 40
```
Render `a` as `png-sequence` alongside `b`+`c` and assert the concatenated frame digests match. Report whether they do; if they do not, the parallel claim in the spec is wrong and must be corrected there rather than quietly dropped.

- [ ] **Step 3: Measure throughput honestly**

Time a 1080p render and record seconds per frame. The spec claims 70.8ms median / 80.7ms p95. Report the measured figure and update the spec if it differs by more than 20%.

- [ ] **Step 4: Full suite**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 5: Version and docs**

Bump `pyproject.toml` and `cli.py` to `1!4.0.0` — Stage 3 is what makes the release honest, since `record` and `export` work again. Update `CHANGELOG.md` with a 4.0.0 section covering the scene engine, `render`, and the removal of `record`. Update `Readme.md`'s usage section. Update `CLAUDE.md`'s module list: `recorder.py` is gone, `render.py`, `timeline.py`, `scene.py`, `compile.py` are new.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml auditorium/cli.py CHANGELOG.md Readme.md CLAUDE.md && git commit -m "chore: auditorium 4.0.0" -- pyproject.toml auditorium/cli.py CHANGELOG.md Readme.md CLAUDE.md
```

---

## Stage 3 done when

- `auditorium render examples/demo_deck.py -o out.mp4` produces a watchable mp4.
- `auditorium export examples/demo_deck.py -f png -o slides/` completes and produces distinct stills.
- `auditorium export examples/demo_deck.py -f pdf` fails fast with the removal rationale, exit code 1.
- Two renders of the same deck are byte-identical.
- A ranged render matches the corresponding frames of a full render.
- `uv run pytest` is green.
- `grep -rn "recorder" auditorium/` returns nothing.

## Deliberately not in Stage 3

- **`--jobs N`.** Frame ranges make parallelism a shell-level fan-out; a managed worker pool is a later convenience.
- **Beat-synced voiceover and multi-track audio.** A single bed only.
- **Alpha output, GIF, cloud rendering, the editor toolkit.**
- **The presenter view**, still broken from Stage 1 — it belongs to Stage 2 along with the preview client.
