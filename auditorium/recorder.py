from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

import typer
import uvicorn


async def record(
    deck_path: Path,
    output: Path,
    resolution: str,
    auto_step: float,
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
                url += f"?auto_step={auto_step}"
            await page.goto(url)

            if live:
                typer.echo(f"Recording live. Navigate with keypresses. Close the browser to stop.")
                await page.wait_for_event("close", timeout=0)
            else:
                typer.echo(f"Recording {len(deck.slides)} slides with {auto_step}s per step...")
                # Wait for the "finished" message via the page's console
                await page.wait_for_function(
                    "() => window.__auditorium_finished === true",
                    timeout=len(deck.slides) * 60 * 1000,  # generous timeout
                )
                typer.echo("All slides recorded.")

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
