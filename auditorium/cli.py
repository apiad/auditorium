from __future__ import annotations

import asyncio
import importlib.util
import json
import signal
import sys
from pathlib import Path

import typer
import uvicorn

from auditorium.console import console

app = typer.Typer(name="auditorium", help="Python-scripted live slide framework")


def _version_callback(value: bool) -> None:
    if value:
        console.print("auditorium [bold]1!4.0.0a1[/]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
) -> None:
    """Python-scripted live slide framework."""
    pass


def _apply_theme_override(
    deck,
    theme: list[str] | None,
    transition: str | None = None,
) -> None:
    """Replace the deck's resolved theme stack and/or transition with CLI values.

    CLI values override the deck's ``theme=`` / ``transition=`` kwargs entirely
    — so ``--theme dark`` on a deck declared with ``theme=["academic", "neon"]``
    yields just ``dark``. Pass nothing to keep the deck's defaults.
    """
    from auditorium.deck import resolve_themes

    if theme:
        try:
            deck.theme_css = resolve_themes(list(theme))
            deck.themes = list(theme)
        except ValueError as e:
            console.print(f"[red]Error:[/] {e}")
            raise typer.Exit(1) from None
    if transition is not None:
        deck.transition = transition


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


def _print_banner(deck, host: str, port: int, presenter: bool = False) -> None:
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
    body.append("\n")
    body.append("Mode:   ", style="dim")
    if presenter:
        body.append("presenter (shared navigation)", style="yellow")
    else:
        body.append("independent (per-tab)", style="dim")

    console.print(Panel(body, title="[bold]Auditorium[/]", border_style="dim"))


@app.command()
def run(
    deck_path: Path = typer.Argument(..., help="Path to the deck.py file"),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser automatically"),
    presenter: bool = typer.Option(False, "-p", "--presenter", help="Also open presenter view"),
    public: bool = typer.Option(False, "--public", help="Share via relay for remote viewers"),
    relay_host: str = typer.Option("vps.apiad.net:4243", "--relay", help="Relay server host:port"),
    public_name: str = typer.Option(None, "--name", help="Custom name for the public URL (e.g. --name my-talk)"),
    watch: bool = typer.Option(True, "--watch/--no-watch", help="Watch for file changes and hot-reload"),
    theme: list[str] = typer.Option(None, "--theme", help="Override the deck theme. Pass multiple times to stack: e.g. --theme academic --theme dark. Each value is a builtin preset name or a path to a .css file."),
    transition: str = typer.Option(None, "--transition", help="Override the slide transition: fade, slide-left, slide-up, zoom, none (or a custom @keyframes name)."),
) -> None:
    """Run a presentation deck."""
    deck_path = deck_path.resolve()
    if not deck_path.exists():
        console.print(f"[red]Error:[/] {deck_path} not found")
        raise typer.Exit(1)

    deck = _load_deck(deck_path)
    _apply_theme_override(deck, theme, transition)
    from auditorium.server import create_app

    application = create_app(deck, presenter_mode=presenter)
    _print_banner(deck, host, port, presenter)

    if watch:
        _setup_watcher(application, deck_path, theme, transition)

    if public:
        _start_relay_bridge(relay_host, port, public_name)

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
    theme: list[str] = typer.Option(None, "--theme", help="Override the deck theme. Pass multiple times to stack."),
    transition: str = typer.Option(None, "--transition", help="Override the slide transition: fade, slide-left, slide-up, zoom, none (or a custom @keyframes name)."),
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
    asyncio.run(do_record(deck_path, output, resolution, auto_step, slide_delay, live, port, theme, transition))


@app.command()
def export(
    deck_path: Path = typer.Argument(..., help="Path to the deck.py file"),
    fmt: str = typer.Option("html", "-f", "--format", help="Output format: html, png"),
    output: Path = typer.Option(None, "-o", "--output", help="Output path (default: deck.html or slides/)"),
    resolution: str = typer.Option("1920x1080", "-r", "--resolution", help="Viewport size, e.g. 1280x720"),
    step_by_step: bool = typer.Option(False, "-s", "--step-by-step", help="One page/frame per step instead of per slide"),
    port: int = typer.Option(0, help="Server port (0 = random)"),
    theme: list[str] = typer.Option(None, "--theme", help="Override the deck theme. Pass multiple times to stack."),
    transition: str = typer.Option(None, "--transition", help="Override the slide transition: fade, slide-left, slide-up, zoom, none (or a custom @keyframes name)."),
) -> None:
    """Export a deck to a self-contained HTML bundle or PNG stills."""
    deck_path = deck_path.resolve()
    if not deck_path.exists():
        console.print(f"[red]Error:[/] {deck_path} not found")
        raise typer.Exit(1)

    if fmt == "pdf":
        console.print(
            "[red]Error:[/] PDF export was removed in 4.0.\n"
            "A timeline has no canonical instant to print: a scene is a "
            "continuous function of time, not a page.\n"
            "Export [bold]png[/] stills and decide yourself what instants "
            "matter, then assemble them (img2pdf, ImageMagick).\n"
            "For a document that was always meant to be printed, author it in "
            "scriptorium instead."
        )
        raise typer.Exit(1)

    if fmt not in ("html", "png"):
        console.print(f"[red]Error:[/] unknown format [bold]'{fmt}'[/]. Use html or png.")
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
    asyncio.run(export_deck(deck_path, output, fmt, resolution, step_by_step, port, theme, transition))


def _start_live_status(application, deck) -> None:
    """Start a background thread that displays live session status.

    Reports connections only. Per-client position used to be here, but the
    server no longer knows it: the browser holds the compiled timeline and
    seeks locally, so asking clients to report back would reintroduce exactly
    the chatter the timeline model removed.
    """
    import threading
    from rich.live import Live
    from rich.table import Table

    def _render():
        table = Table(show_header=True, header_style="dim", box=None, padding=(0, 1))
        table.add_column("Mode", style="dim", width=12)
        table.add_column("Connections", width=16)
        table.add_column("Scenes", width=8)
        table.add_column("Presenter", width=14)

        total = len(deck.slides) if deck else 0

        if application.state.presenter_mode:
            pres = application.state.shared_pres
            n = len(pres.audience_clients)
            conns = f"{n} tab{'s' if n != 1 else ''}" if n else "[dim]none[/]"
            presenter = "[green]connected[/]" if pres.presenter_ws else "[dim]none[/]"
            table.add_row("shared", conns, str(total), presenter)
        else:
            n = len(application.state.sessions)
            conns = f"{n} tab{'s' if n != 1 else ''}" if n else "[dim]none[/]"
            table.add_row("independent", conns, str(total), "[dim]n/a[/]")

        return table

    def _run():
        import time
        time.sleep(1)
        with Live(_render(), console=console, refresh_per_second=2, transient=True) as live:
            while True:
                time.sleep(0.5)
                live.update(_render())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


@app.command()
def relay(
    port: int = typer.Option(4243, help="Port to bind to"),
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
) -> None:
    """Run a relay server for public presentation sharing."""
    from auditorium.relay import create_relay_app

    relay_app = create_relay_app()
    console.print(f"[bold]Auditorium Relay[/] listening on [cyan]{host}:{port}[/]")
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    uvicorn.run(relay_app, host=host, port=port, log_level="warning")


def _start_relay_bridge(relay_host: str, local_port: int, name: str | None = None) -> None:
    """Connect to a relay server and bridge the local presentation to it."""
    import threading

    def _bridge():
        import time
        from websockets.sync.client import connect as ws_connect

        time.sleep(1.5)  # Wait for local server to start

        relay_protocol = "wss" if ":443" in relay_host else "ws"
        http_protocol = "https" if relay_protocol == "wss" else "http"

        try:
            # Connect to the relay as an upstream presenter
            relay_ws = ws_connect(f"{relay_protocol}://{relay_host}/upstream")

            # Send registration with optional custom name
            register_msg = {"type": "register"}
            if name:
                register_msg["name"] = name
            relay_ws.send(json.dumps(register_msg))

            reg = json.loads(relay_ws.recv())
            if reg.get("type") == "error":
                console.print(f"[red]Relay error:[/] {reg.get('message')}")
                return
            if reg.get("type") != "registered":
                console.print("[red]Relay error:[/] unexpected response")
                return

            session_id = reg["id"]
            public_url = f"{http_protocol}://{relay_host}/r/{session_id}/"
            console.print(f"\n[green]Public URL:[/] [bold cyan]{public_url}[/]\n")

            # Connect to the local server as an audience client
            local_ws = ws_connect(f"ws://127.0.0.1:{local_port}/ws")
            local_ws.send(json.dumps({"type": "hello", "slide": 0}))

            # Two threads: local→relay and relay→local
            def forward_local_to_relay():
                try:
                    while True:
                        data = local_ws.recv()
                        relay_ws.send(data)
                except Exception:
                    pass

            def forward_relay_to_local():
                try:
                    while True:
                        data = relay_ws.recv()
                        local_ws.send(data)
                except Exception:
                    pass

            t1 = threading.Thread(target=forward_local_to_relay, daemon=True)
            t2 = threading.Thread(target=forward_relay_to_local, daemon=True)
            t1.start()
            t2.start()
            t1.join()

        except Exception as e:
            console.print(f"[red]Relay error:[/] {e}")

    thread = threading.Thread(target=_bridge, daemon=True)
    thread.start()


def _setup_watcher(
    application,
    deck_path: Path,
    theme: list[str] | None = None,
    transition: str | None = None,
) -> None:
    """Set up a file watcher that hot-reloads the deck on changes."""
    import threading
    from watchfiles import watch as watch_files

    def _watch():
        watch_dir = deck_path.parent
        for _changes in watch_files(watch_dir, watch_filter=_python_filter):
            console.print("[yellow]⟳[/] Change detected, reloading...")
            try:
                new_deck = _load_deck(deck_path)
                _apply_theme_override(new_deck, theme, transition)
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
