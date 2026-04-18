from __future__ import annotations

import asyncio
import importlib.util
import signal
import sys
from pathlib import Path

import typer
import uvicorn

from auditorium.console import console

app = typer.Typer(name="auditorium", help="Python-scripted live slide framework")


def _version_callback(value: bool) -> None:
    if value:
        console.print("auditorium [bold]1!3.0.0[/]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
) -> None:
    """Python-scripted live slide framework."""
    pass


def _load_deck(deck_path: Path):
    """Import a deck.py file and find the Deck instance."""
    from auditorium.deck import Deck

    module_name = f"_deck_{id(deck_path)}"
    spec = importlib.util.spec_from_file_location(module_name, deck_path)
    if spec is None or spec.loader is None:
        console.print(f"[red]Error:[/] cannot load {deck_path}")
        raise typer.Exit(1)
    module = importlib.util.module_from_spec(spec)
    deck_dir = str(deck_path.parent.resolve())
    if deck_dir not in sys.path:
        sys.path.insert(0, deck_dir)
    spec.loader.exec_module(module)
    for attr in dir(module):
        obj = getattr(module, attr)
        if isinstance(obj, Deck):
            return obj
    console.print(f"[red]Error:[/] no Deck instance found in {deck_path}")
    raise typer.Exit(1)


def _print_banner(deck, host: str, port: int) -> None:
    """Print a startup banner with deck info."""
    from rich.panel import Panel
    from rich.text import Text

    body = Text()
    body.append("Deck:   ", style="dim")
    body.append(deck.title, style="bold")
    body.append("\n")
    body.append("Slides: ", style="dim")
    body.append(str(len(deck.slides)))
    body.append("\n")
    body.append("URL:    ", style="dim")
    body.append(f"http://{host}:{port}", style="bold cyan")

    console.print(Panel(body, title="[bold]Auditorium[/]", border_style="dim"))


@app.command()
def run(
    deck_path: Path = typer.Argument(..., help="Path to the deck.py file"),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser automatically"),
    presenter: bool = typer.Option(False, "--presenter", help="Also open presenter view"),
    watch: bool = typer.Option(True, "--watch/--no-watch", help="Watch for file changes and hot-reload"),
) -> None:
    """Run a presentation deck."""
    deck_path = deck_path.resolve()
    if not deck_path.exists():
        console.print(f"[red]Error:[/] {deck_path} not found")
        raise typer.Exit(1)

    deck = _load_deck(deck_path)
    from auditorium.server import create_app

    application = create_app(deck)
    _print_banner(deck, host, port)

    if watch:
        _setup_watcher(application, deck_path)

    if open_browser:
        import webbrowser
        import threading

        def _open():
            import time
            time.sleep(0.5)
            webbrowser.open(f"http://{host}:{port}")
            if presenter:
                time.sleep(0.3)
                webbrowser.open(f"http://{host}:{port}/presenter")

        threading.Thread(target=_open, daemon=True).start()

    _start_live_status(application, deck)

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    uvicorn.run(application, host=host, port=port, log_level="warning")


@app.command()
def record(
    deck_path: Path = typer.Argument(..., help="Path to the deck.py file"),
    output: Path = typer.Option("recording.webm", "-o", "--output", help="Output file path"),
    resolution: str = typer.Option("1920x1080", help="Viewport size, e.g. 1280x720"),
    auto_step: float = typer.Option(2.0, "-a", "--auto-step", help="Seconds per step() in auto mode"),
    slide_delay: float = typer.Option(3.0, "-d", "--slide-delay", help="Seconds to linger on completed slide before advancing"),
    live: bool = typer.Option(False, "--live", help="Launch visible browser for manual recording"),
    port: int = typer.Option(0, help="Server port (0 = random)"),
) -> None:
    """Record a presentation to video."""
    deck_path = deck_path.resolve()
    if not deck_path.exists():
        console.print(f"[red]Error:[/] {deck_path} not found")
        raise typer.Exit(1)

    if port == 0:
        import socket
        with socket.socket() as s:
            s.bind(("", 0))
            port = s.getsockname()[1]

    from auditorium.recorder import record as do_record
    asyncio.run(do_record(deck_path, output, resolution, auto_step, slide_delay, live, port))


@app.command()
def export(
    deck_path: Path = typer.Argument(..., help="Path to the deck.py file"),
    fmt: str = typer.Option("pdf", "-f", "--format", help="Output format: pdf, html, png"),
    output: Path = typer.Option(None, "-o", "--output", help="Output path (default: deck.pdf/html or slides/)"),
    resolution: str = typer.Option("1920x1080", "-r", "--resolution", help="Viewport size, e.g. 1280x720"),
    step_by_step: bool = typer.Option(False, "-s", "--step-by-step", help="One page/frame per step instead of per slide"),
    port: int = typer.Option(0, help="Server port (0 = random)"),
) -> None:
    """Export presentation to PDF, HTML, or PNG."""
    deck_path = deck_path.resolve()
    if not deck_path.exists():
        console.print(f"[red]Error:[/] {deck_path} not found")
        raise typer.Exit(1)

    if fmt not in ("pdf", "html", "png"):
        console.print(f"[red]Error:[/] unknown format [bold]'{fmt}'[/]. Use pdf, html, or png.")
        raise typer.Exit(1)

    if output is None:
        stem = deck_path.stem
        if fmt == "png":
            output = Path(f"{stem}-slides")
        else:
            output = Path(f"{stem}.{fmt}")

    if port == 0:
        import socket
        with socket.socket() as s:
            s.bind(("", 0))
            port = s.getsockname()[1]

    from auditorium.exporter import export_deck
    asyncio.run(export_deck(deck_path, output, fmt, resolution, step_by_step, port))


def _start_live_status(application, deck) -> None:
    """Start a background thread that displays live session status."""
    import threading
    from rich.live import Live
    from rich.table import Table

    def _render():
        table = Table(show_header=True, header_style="dim", box=None, padding=(0, 1))
        table.add_column("Session", style="dim", width=8)
        table.add_column("Slide", width=20)
        table.add_column("Status", width=10)

        sessions = getattr(application.state, "sessions", {})
        if not sessions:
            table.add_row("", "[dim]No connections[/]", "")
        else:
            for i, (sid, session) in enumerate(sessions.items()):
                slide_idx = session.current_slide
                total = len(deck.slides) if deck else 0
                slide_name = ""
                if deck and slide_idx < len(deck.slides):
                    slide_name = deck.slides[slide_idx].name
                task_status = "idle"
                if session.slide_task and not session.slide_task.done():
                    task_status = "[green]running[/]"
                elif session.step_event:
                    task_status = "[yellow]waiting[/]"
                table.add_row(
                    f"#{i + 1}",
                    f"{slide_idx + 1}/{total} [dim]{slide_name}[/]",
                    task_status,
                )
        return table

    def _run():
        import time
        # Wait for server to start
        time.sleep(1)
        with Live(_render(), console=console, refresh_per_second=2, transient=True) as live:
            while True:
                time.sleep(0.5)
                live.update(_render())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def _setup_watcher(application, deck_path: Path) -> None:
    """Set up a file watcher that hot-reloads the deck on changes."""
    import threading
    from watchfiles import watch as watch_files

    def _watch():
        watch_dir = deck_path.parent
        for _changes in watch_files(watch_dir, watch_filter=_python_filter):
            console.print("[yellow]⟳[/] Change detected, reloading...")
            try:
                new_deck = _load_deck(deck_path)
                loop = getattr(application.state, "loop", None)
                if loop and loop.is_running():
                    from auditorium.server import reload_deck
                    asyncio.run_coroutine_threadsafe(
                        reload_deck(application, new_deck), loop
                    )
            except Exception as e:
                console.print(f"[red]Reload error:[/] {e}")

    thread = threading.Thread(target=_watch, daemon=True)
    thread.start()


def _python_filter(change, path: str) -> bool:
    """Only watch Python files."""
    return path.endswith(".py")
