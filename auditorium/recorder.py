from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

import typer
import uvicorn
from tqdm import tqdm


async def record(
    deck_path: Path,
    output: Path,
    resolution: str,
    auto_step: float,
    slide_delay: float,
    live: bool,
    port: int,
) -> None:
    """Record a presentation to video."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        typer.echo(
            "Recording requires playwright. Install with:\n"
            "  pip install auditorium[record]\n"
            "  playwright install chromium",
            err=True,
        )
        raise typer.Exit(1)

    from auditorium.cli import _load_deck
    from auditorium.server import create_app

    # Load deck and create app
    deck = _load_deck(deck_path)
    app = create_app(deck)

    # Start uvicorn programmatically
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    # Wait for server to start
    while not server.started:
        await asyncio.sleep(0.05)

    width, height = _parse_resolution(resolution)
    tmpdir = tempfile.mkdtemp(prefix="auditorium-record-")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not live)
            context = await browser.new_context(
                viewport={"width": width, "height": height},
                record_video_dir=tmpdir,
                record_video_size={"width": width, "height": height},
            )
            page = await context.new_page()
            url = f"http://127.0.0.1:{port}/"
            if not live:
                url += f"?auto_step={auto_step}&slide_delay={slide_delay}"
            await page.goto(url)

            if live:
                typer.echo("Recording live. Navigate with keypresses. Close the browser to stop.")
                await page.wait_for_event("close", timeout=0)
            else:
                total = len(deck.slides)
                with tqdm(total=total, desc="Recording", unit="slide") as pbar:
                    last_slide = -1
                    while True:
                        finished = await page.evaluate(
                            "() => window.__auditorium_finished === true"
                        )
                        if finished:
                            pbar.update(total - pbar.n)
                            break
                        current = await page.evaluate(
                            "() => { const el = document.getElementById('slide-indicator'); "
                            "if (!el) return 0; const m = el.textContent.match(/(\\d+)/); "
                            "return m ? parseInt(m[1]) : 0; }"
                        )
                        if current > last_slide:
                            pbar.update(current - last_slide)
                            last_slide = current
                        await asyncio.sleep(0.3)

            await context.close()
            await browser.close()

        # Find the recorded video and move it to the output path
        video_files = list(Path(tmpdir).glob("*.webm"))
        if video_files:
            src = video_files[0]
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(output))
            typer.echo(f"Video saved to {output}")
        else:
            typer.echo("Error: no video file produced", err=True)
    finally:
        server.should_exit = True
        await server_task
        shutil.rmtree(tmpdir, ignore_errors=True)


def _parse_resolution(resolution: str) -> tuple[int, int]:
    """Parse '1920x1080' into (1920, 1080)."""
    parts = resolution.lower().split("x")
    if len(parts) != 2:
        raise typer.BadParameter(f"Invalid resolution: {resolution}. Use WIDTHxHEIGHT, e.g. 1920x1080")
    return int(parts[0]), int(parts[1])
