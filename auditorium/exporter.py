from __future__ import annotations

import asyncio
import base64
import shutil
import tempfile
from pathlib import Path

import typer
import uvicorn

from auditorium.console import console


async def export_deck(
    deck_path: Path,
    output: Path,
    fmt: str,
    resolution: str,
    step_by_step: bool,
    port: int,
    theme: list[str] | None = None,
    transition: str | None = None,
) -> None:
    """Export a presentation to PDF, HTML, or PNG.

    The *step_by_step* parameter is accepted for forward compatibility but is
    not yet implemented -- the current version always captures the final DOM
    state of each slide.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        console.print(
            "[red]Error:[/] Export requires playwright. Install with:\n"
            "  [bold]pip install auditorium\\[record][/]\n"
            "  [bold]playwright install chromium[/]"
        )
        raise typer.Exit(1)

    from auditorium.cli import _load_deck
    from auditorium.server import STATIC_DIR, create_app

    from auditorium.cli import _apply_theme_override

    deck = _load_deck(deck_path)
    _apply_theme_override(deck, theme, transition)
    app = create_app(deck)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    while not server.started:
        await asyncio.sleep(0.05)

    # port=0 asks the OS for a free port; the URL needs the one it actually got.
    bound_port = server.servers[0].sockets[0].getsockname()[1]

    width, height = _parse_resolution(resolution)
    tmpdir = tempfile.mkdtemp(prefix="auditorium-export-")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": width, "height": height})

            if fmt == "png":
                output.mkdir(parents=True, exist_ok=True)

            slide_doms: list[dict] = []

            from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn

            # CSS that kills all animations/transitions so exports capture
            # final state without mid-animation artifacts.
            DISABLE_ANIM_CSS = """
                *, *::before, *::after {
                    animation-duration: 0s !important;
                    animation-delay: 0s !important;
                    transition-duration: 0s !important;
                    transition-delay: 0s !important;
                }
                /* The connection dot reports a live WebSocket. In a still it
                   is a green speck of nothing, so it does not belong there. */
                #connection-status { display: none !important; }
            """

            # The deck is a timeline now, not a sequence of slide URLs: load the
            # page once and seek to each beat. The old drive path asked for
            # ?auto_step=0&instant_sleep=1 -- parameters the 4.0 server no longer
            # parses -- and then waited on window.__auditorium_slide_complete,
            # which the 4.0 client never sets. It hung for the full 120s timeout.
            await page.goto(f"http://127.0.0.1:{bound_port}/", wait_until="load")
            await page.wait_for_function(
                "() => window.__auditorium_ready === true", timeout=30000
            )
            await page.evaluate("async () => { await document.fonts.ready; }")
            await page.add_style_tag(content=DISABLE_ANIM_CSS)

            beat_times = await page.evaluate(
                "() => window.AuditoriumEngine._tl.beats.map(b => b.t)"
            )
            duration_ms = await page.evaluate(
                "() => window.AuditoriumEngine._tl.meta.duration_ms"
            )
            # Scene boundaries emit a beat where the *outgoing* scene is still
            # whole -- the clear lands a millisecond later. So the final scene
            # sits after the last beat and has no beat of its own: without the
            # end state a two-scene deck would export only the first scene. A
            # deck with no beats at all is still this one capturable frame.
            stops = list(beat_times)
            if not stops or stops[-1] != duration_ms:
                stops.append(duration_ms)

            with Progress(
                TextColumn("[bold]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"Exporting {fmt.upper()}", total=len(stops))
                for i, t in enumerate(stops):
                    # Drive through the client's seek wrapper, not the engine
                    # directly: the wrapper also updates chrome, and skipping
                    # it freezes the slide indicator at its load-time value on
                    # every captured frame.
                    await page.evaluate(
                        "(t) => (window.__auditoriumShow || window.AuditoriumEngine.seek)(t)",
                        t,
                    )
                    await _capture(page, fmt, output, slide_doms, i, None)
                    progress.update(task, advance=1)

            await browser.close()

        if fmt == "html":
            _build_html(slide_doms, output, width, height, STATIC_DIR, deck.theme_style_block())
            console.print(f"[green]✓[/] HTML saved to [bold]{output}[/]")
        elif fmt == "png":
            console.print(f"[green]✓[/] PNG slides saved to [bold]{output}/[/]")

    finally:
        server.should_exit = True
        await server_task
        shutil.rmtree(tmpdir, ignore_errors=True)


def _build_html(
    slide_doms: list[dict],
    output: Path,
    width: int,
    height: int,
    static_dir: Path,
    theme_overrides: str = "",
) -> None:
    """Build a self-contained HTML file with all slides and a JS navigator."""
    theme_css = (static_dir / "theme.css").read_text()
    katex_css = _inline_katex_fonts(
        (static_dir / "vendor" / "katex" / "katex.min.css").read_text(),
        static_dir / "vendor" / "katex" / "fonts",
    )
    hljs_css = (static_dir / "vendor" / "hljs" / "styles" / "github.min.css").read_text()

    # Inline Google Fonts as base64 data URLs
    font_faces = ""
    for font_file in sorted((static_dir / "fonts").glob("*.woff2")):
        b64 = base64.b64encode(font_file.read_bytes()).decode()
        name = font_file.stem.replace("-latin", "").replace("-", " ").title()
        font_faces += (
            f"@font-face {{ font-family: '{name}'; "
            f"src: url(data:font/woff2;base64,{b64}) format('woff2'); "
            f"font-weight: 300 700; font-display: block; }}\n"
        )

    slides_html = ""
    slide_num = 0
    for i, dom in enumerate(slide_doms):
        active = " active" if i == 0 else ""
        boundary = dom.get("boundary", "initial")
        duration = dom.get("duration", 0)
        if boundary == "initial":
            slide_num += 1
        slides_html += (
            f'<div class="export-slide{active} {dom["classes"]}" '
            f'data-boundary="{boundary}" data-duration="{duration}" data-slide="{slide_num}">'
            f'{dom["html"]}</div>\n'
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Exported Presentation</title>
<style>
{font_faces}
{theme_css}
{katex_css}
{hljs_css}
.export-slide {{
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem;
    font-size: 1.5rem;
    line-height: 1.8;
}}
body {{ margin: 0; background: #fff; overflow: hidden; }}
.export-slide {{ position: absolute; top: 0; left: 0; opacity: 0; transition: opacity 0.25s ease; pointer-events: none; }}
.export-slide.active {{ opacity: 1; pointer-events: auto; }}
#counter {{ position: fixed; bottom: 1rem; right: 1rem; font: 0.875rem monospace; color: #9ca3af; z-index: 10; }}
</style>
{theme_overrides}
</head>
<body>
{slides_html}
<div id="counter">1 / {len(slide_doms)}</div>
<script>
(function() {{
    const slides = document.querySelectorAll('.export-slide');
    const counter = document.getElementById('counter');
    let current = 0;
    let autoTimer = null;

    function show(n) {{
        n = Math.max(0, Math.min(n, slides.length - 1));
        if (n === current) return;
        // Cancel any pending auto-advance
        if (autoTimer) {{ clearTimeout(autoTimer); autoTimer = null; }}
        slides[current].classList.remove('active');
        slides[n].classList.add('active');
        current = n;
        counter.textContent = (current + 1) + ' / ' + slides.length;
        // Check if the NEXT frame is a sleep boundary — if so, auto-advance
        scheduleAuto();
    }}

    function scheduleAuto() {{
        if (current + 1 >= slides.length) return;
        const next = slides[current + 1];
        if (next.dataset.boundary === 'sleep') {{
            const dur = parseFloat(next.dataset.duration) || 0.5;
            autoTimer = setTimeout(function() {{ show(current + 1); }}, dur * 1000);
        }}
    }}

    function prevSlide() {{
        // Go to the first frame of the previous slide (consistent with live mode)
        const curSlide = slides[current].dataset.slide;
        // Find the first frame of the current slide
        let firstOfCurrent = current;
        while (firstOfCurrent > 0 && slides[firstOfCurrent - 1].dataset.slide === curSlide) {{
            firstOfCurrent--;
        }}
        if (firstOfCurrent === current && firstOfCurrent > 0) {{
            // Already at first frame of this slide — go to first frame of previous slide
            const prevSlideNum = slides[firstOfCurrent - 1].dataset.slide;
            let target = firstOfCurrent - 1;
            while (target > 0 && slides[target - 1].dataset.slide === prevSlideNum) {{
                target--;
            }}
            show(target);
        }} else {{
            // Go to first frame of current slide (restart slide)
            show(firstOfCurrent);
        }}
    }}

    document.addEventListener('keydown', function(e) {{
        if (e.key === 'ArrowRight' || e.key === ' ') {{ e.preventDefault(); show(current + 1); }}
        else if (e.key === 'ArrowLeft') {{ e.preventDefault(); prevSlide(); }}
    }});

    // Start auto-advance chain if the second frame is a sleep
    scheduleAuto();
}})();
</script>
</body>
</html>"""
    )


def _inline_katex_fonts(katex_css: str, font_dir: Path) -> str:
    """Replace KaTeX font url() references with base64 data URIs."""
    import re

    def _replace(match: re.Match) -> str:
        font_path = font_dir / match.group(1)
        if font_path.exists():
            b64 = base64.b64encode(font_path.read_bytes()).decode()
            ext = font_path.suffix.lstrip(".")
            mime = {"woff2": "font/woff2", "woff": "font/woff", "ttf": "font/ttf"}.get(ext, "font/woff2")
            return f"url(data:{mime};base64,{b64})"
        return match.group(0)

    result = re.sub(r'url\(fonts/([^)]+)\)', _replace, katex_css)
    # Remove remaining non-inlined font references (woff/ttf fallbacks we don't have)
    result = re.sub(r',\s*url\(fonts/[^)]+\)\s*format\([^)]+\)', '', result)
    result = re.sub(r'url\(fonts/[^)]+\)\s*format\([^)]+\)\s*,?', '', result)
    return result


async def _capture(page, fmt: str, output: Path, slide_doms: list[dict], slide_idx: int, step_idx: int | None) -> None:
    """Capture the current DOM state as PNG or DOM dict with boundary metadata."""
    # Let the browser finish any remaining layout/paint work
    await page.wait_for_timeout(100)
    if fmt == "png":
        suffix = f"-step{step_idx + 1:02d}" if step_idx is not None else ""
        await page.screenshot(path=str(output / f"slide-{slide_idx + 1:03d}{suffix}.png"))
    else:
        dom = await page.evaluate(
            """() => {
            const root = document.getElementById('slide-root');
            const boundary = window.__auditorium_last_boundary || {type: 'initial'};
            return {
                html: root.innerHTML,
                classes: root.className,
                boundary: boundary.type,
                duration: boundary.duration || 0,
            };
        }"""
        )
        slide_doms.append(dom)


def _parse_resolution(resolution: str) -> tuple[int, int]:
    """Parse '1920x1080' into (1920, 1080)."""
    parts = resolution.lower().split("x")
    if len(parts) != 2:
        raise typer.BadParameter(f"Invalid resolution: {resolution}")
    return int(parts[0]), int(parts[1])
