from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

import typer
import uvicorn

from auditorium.console import console


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
        console.print(
            "[red]Error:[/] Recording requires playwright. Install with:\n"
            "  [bold]pip install auditorium\\[record][/]\n"
            "  [bold]playwright install chromium[/]"
        )
        raise typer.Exit(1)

    from auditorium.cli import _load_deck
    from auditorium.server import create_app

    deck = _load_deck(deck_path)
    app = create_app(deck)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

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
                console.print("Recording [bold]live[/]. Navigate with keypresses. Close the browser to stop.")
                await page.wait_for_event("close", timeout=0)
            else:
                from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn

                total = len(deck.slides)
                with Progress(
                    TextColumn("[bold]{task.description}"),
                    BarColumn(),
                    TextColumn("{task.completed}/{task.total} slides"),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task("Recording", total=total)
                    last_slide = -1
                    while True:
                        finished = await page.evaluate(
                            "() => window.__auditorium_finished === true"
                        )
                        if finished:
                            progress.update(task, completed=total)
                            break
                        current = await page.evaluate(
                            "() => { const el = document.getElementById('slide-indicator'); "
                            "if (!el) return 0; const m = el.textContent.match(/(\\d+)/); "
                            "return m ? parseInt(m[1]) : 0; }"
                        )
                        if current > last_slide:
                            progress.update(task, completed=current)
                            last_slide = current
                        await asyncio.sleep(0.3)

            await context.close()
            await browser.close()

        video_files = list(Path(tmpdir).glob("*.webm"))
        if video_files:
            src = video_files[0]
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(output))
            console.print(f"[green]✓[/] Video saved to [bold]{output}[/]")
        else:
            console.print("[red]✗[/] No video file produced")
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
