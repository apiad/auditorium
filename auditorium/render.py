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
    # A deck with no ops, tracks or beats has a zero-length schedule, but it is
    # still one capturable state. Rendering it as nothing leaves a caller
    # holding an empty directory and no way to tell that from a failure.
    schedule = render_schedule(timeline, fps) or [0]
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
            # The dot reports a live WebSocket, and which state it is in when a
            # frame is taken depends on how fast the socket happened to open --
            # a wall clock reaching the image by the back door.
            await page.add_style_tag(
                content="#connection-status { display: none !important; }"
            )

            for index in range(stop):
                t = schedule[index]
                # Drive through the client's seek wrapper. It clears the
                # autoplay the page starts on load -- whose rAF loop reads
                # performance.now() and would overwrite this seek before the
                # screenshot -- and it advances the chrome, which seeking the
                # engine directly leaves frozen at its load-time value.
                await page.evaluate(
                    "(t) => (window.__auditoriumShow || window.AuditoriumEngine.seek)(t)",
                    t,
                )
                if index < start_frame:
                    continue
                # No animations="disabled" here: it fast-forwards every finite
                # animation to its end state, which is the one state this frame
                # is not in. The engine already pins determinism itself -- seek()
                # pauses every animation on the page and sets currentTime = t.
                await page.screenshot(
                    path=str(out_dir / FRAME_NAME.format(index)),
                )
                written += 1
            await context.close()
            await browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)

    return written


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
