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

    deck = _load_deck(deck_path)
    app = create_app(deck)
    total = len(deck.slides)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    while not server.started:
        await asyncio.sleep(0.05)

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
            """

            with Progress(
                TextColumn("[bold]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"Exporting {fmt.upper()}", total=total)
                for i in range(total):
                    if step_by_step:
                        # Step-by-step: no auto_step (steps block), instant_sleep.
                        # We drive each step via keypress and capture between each.
                        url = f"http://127.0.0.1:{port}/?instant_sleep=1&slide_delay=9999&_s={i}#slide-{i}"
                        await page.goto(url, wait_until="load")
                        await page.add_style_tag(content=DISABLE_ANIM_CSS)

                        step_idx = 0
                        while True:
                            # Wait for DOM to settle
                            await page.wait_for_timeout(200)

                            # Check if slide already completed
                            done = await page.evaluate(
                                "() => window.__auditorium_slide_complete === true"
                            )
                            # Capture current state
                            await _capture(page, fmt, output, slide_doms, i, step_idx)
                            step_idx += 1

                            if done:
                                break

                            # Advance one step/sleep boundary by sending a keypress
                            await page.keyboard.press("ArrowRight")
                            # Wait for the step/sleep to resolve and new content to render.
                            # Use a short poll: either step_count changes, slide completes,
                            # or we timeout after 2s (handles slides that finish between
                            # steps without sending step_complete).
                            prev_count = await page.evaluate(
                                "() => window.__auditorium_step_count || 0"
                            )
                            try:
                                await page.wait_for_function(
                                    f"() => (window.__auditorium_step_count || 0) > {prev_count} "
                                    f"|| window.__auditorium_slide_complete === true",
                                    timeout=2000,
                                )
                            except Exception:
                                # Timeout is OK — slide may have completed between checks
                                pass

                        progress.update(task, advance=1)
                    else:
                        # Default: auto_step=0 + instant_sleep — everything runs
                        # instantly, capture final state.
                        url = f"http://127.0.0.1:{port}/?auto_step=0&instant_sleep=1&slide_delay=9999&_s={i}#slide-{i}"
                        await page.goto(url, wait_until="load")
                        await page.add_style_tag(content=DISABLE_ANIM_CSS)
                        await page.wait_for_function(
                            "() => window.__auditorium_slide_complete === true",
                            timeout=120000,
                        )
                        await _capture(page, fmt, output, slide_doms, i, None)
                        progress.update(task, advance=1)

            await browser.close()

        if fmt == "html":
            _build_html(slide_doms, output, width, height, STATIC_DIR)
            console.print(f"[green]✓[/] HTML saved to [bold]{output}[/]")
        elif fmt == "pdf":
            await _build_pdf(slide_doms, output, width, height, STATIC_DIR, tmpdir)
            console.print(f"[green]✓[/] PDF saved to [bold]{output}[/]")
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
) -> None:
    """Build a self-contained HTML file with all slides and a JS navigator."""
    theme_css = (static_dir / "theme.css").read_text()
    katex_css = (static_dir / "vendor" / "katex" / "katex.min.css").read_text()
    hljs_css = (static_dir / "vendor" / "hljs" / "styles" / "github.min.css").read_text()

    # Inline fonts as base64 data URLs
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
    for i, dom in enumerate(slide_doms):
        active = " active" if i == 0 else ""
        slides_html += (
            f'<div class="export-slide{active} {dom["classes"]}">'
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
</head>
<body>
{slides_html}
<div id="counter">1 / {len(slide_doms)}</div>
<script>
(function() {{
    const slides = document.querySelectorAll('.export-slide');
    const counter = document.getElementById('counter');
    let current = 0;
    // Show the first slide
    slides[0].classList.add('active');
    function show(n) {{
        n = Math.max(0, Math.min(n, slides.length - 1));
        if (n === current) return;
        slides[current].classList.remove('active');
        slides[n].classList.add('active');
        current = n;
        counter.textContent = (current + 1) + ' / ' + slides.length;
    }}
    document.addEventListener('keydown', function(e) {{
        if (e.key === 'ArrowRight' || e.key === ' ') {{ e.preventDefault(); show(current + 1); }}
        else if (e.key === 'ArrowLeft') {{ e.preventDefault(); show(current - 1); }}
    }});
}})();
</script>
</body>
</html>"""
    )


async def _build_pdf(
    slide_doms: list[dict],
    output: Path,
    width: int,
    height: int,
    static_dir: Path,
    tmpdir: str,
) -> None:
    """Build a vector PDF by rendering slides in a print-optimized page."""
    from playwright.async_api import async_playwright

    theme_css = (static_dir / "theme.css").read_text()
    katex_css = (static_dir / "vendor" / "katex" / "katex.min.css").read_text()
    hljs_css = (static_dir / "vendor" / "hljs" / "styles" / "github.min.css").read_text()

    slides_html = ""
    for i, dom in enumerate(slide_doms):
        pb = "page-break-after: always;" if i < len(slide_doms) - 1 else ""
        slides_html += (
            f'<div class="{dom["classes"]}" style="width:{width}px;height:{height}px;'
            f"overflow:hidden;display:flex;flex-direction:column;align-items:center;"
            f'justify-content:center;padding:3rem;font-size:1.5rem;line-height:1.8;{pb}">'
            f'{dom["html"]}</div>\n'
        )

    no_anim = (
        "*, *::before, *::after { "
        "animation-duration: 0s !important; animation-delay: 0s !important; "
        "transition-duration: 0s !important; transition-delay: 0s !important; }"
    )
    print_html = (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">'
        f"<style>{theme_css}\n{katex_css}\n{hljs_css}\n{no_anim}\nbody {{ margin: 0; }}</style>"
        f"</head><body>{slides_html}</body></html>"
    )

    html_path = Path(tmpdir) / "print.html"
    html_path.write_text(print_html)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"file://{html_path}")
        await page.wait_for_timeout(1000)
        output.parent.mkdir(parents=True, exist_ok=True)
        await page.pdf(
            path=str(output),
            width=f"{width}px",
            height=f"{height}px",
            print_background=True,
        )
        await browser.close()


async def _capture(page, fmt: str, output: Path, slide_doms: list[dict], slide_idx: int, step_idx: int | None) -> None:
    """Capture the current DOM state as PNG or DOM dict."""
    # Let the browser finish any remaining layout/paint work
    await page.wait_for_timeout(100)
    if fmt == "png":
        suffix = f"-step{step_idx + 1:02d}" if step_idx is not None else ""
        await page.screenshot(path=str(output / f"slide-{slide_idx + 1:03d}{suffix}.png"))
    else:
        dom = await page.evaluate(
            """() => {
            const root = document.getElementById('slide-root');
            return { html: root.innerHTML, classes: root.className };
        }"""
        )
        slide_doms.append(dom)


def _parse_resolution(resolution: str) -> tuple[int, int]:
    """Parse '1920x1080' into (1920, 1080)."""
    parts = resolution.lower().split("x")
    if len(parts) != 2:
        raise typer.BadParameter(f"Invalid resolution: {resolution}")
    return int(parts[0]), int(parts[1])
