from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from auditorium.deck import Deck

STATIC_DIR = Path(__file__).parent / "static"


@dataclass
class Presentation:
    """Shared presentation state. All audience tabs + presenter share one slide state."""

    audience_clients: list[WebSocket] = field(default_factory=list)
    presenter_ws: WebSocket | None = None
    slide_task: asyncio.Task | None = None
    current_slide: int = 0
    step_event: asyncio.Event | None = None
    numeric_buffer: str = ""
    pending_acks: dict[str, asyncio.Event] = field(default_factory=dict)
    auto_step: float | None = None
    slide_delay: float = 3.0
    instant_sleep: bool = False

    async def send(self, message: dict) -> None:
        """Send a JSON message to all connected clients (audience + presenter)."""
        data = json.dumps(message)
        for ws in list(self.audience_clients):
            try:
                await ws.send_text(data)
            except Exception:
                self.audience_clients.remove(ws)
        if self.presenter_ws:
            try:
                await self.presenter_ws.send_text(data)
            except Exception:
                self.presenter_ws = None

    async def send_mutation(self, mutation: dict) -> None:
        """Send a mutation and wait for acknowledgment from any client."""
        mutation_id = str(uuid.uuid4())
        mutation["id"] = mutation_id
        mutation["type"] = "mutation"
        event = asyncio.Event()
        self.pending_acks[mutation_id] = event
        await self.send(mutation)
        if self.audience_clients or self.presenter_ws:
            try:
                await event.wait()
            except asyncio.CancelledError:
                self.pending_acks.pop(mutation_id, None)
                raise

    def cancel_slide(self) -> None:
        """Cancel the current slide task if running."""
        if self.slide_task and not self.slide_task.done():
            self.slide_task.cancel()
        self.slide_task = None
        self.step_event = None

    @property
    def has_clients(self) -> bool:
        return bool(self.audience_clients) or self.presenter_ws is not None


def create_app(deck: Deck | None = None) -> FastAPI:
    app = FastAPI()
    app.state.deck = deck
    app.state.presentation = Presentation()

    @app.on_event("startup")
    async def _capture_loop() -> None:
        app.state.loop = asyncio.get_running_loop()

    @app.on_event("shutdown")
    async def _cleanup() -> None:
        app.state.presentation.cancel_slide()

    @app.get("/")
    async def index() -> HTMLResponse:
        html = (STATIC_DIR / "index.html").read_text()
        return HTMLResponse(html)

    @app.get("/presenter")
    async def presenter_page() -> HTMLResponse:
        html = (STATIC_DIR / "presenter.html").read_text()
        return HTMLResponse(html)

    # Serve all static assets (CSS, JS, fonts, vendor libs)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        pres = app.state.presentation
        is_presenter = False

        try:
            # Wait for the client's hello message
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg.get("type") != "hello":
                await ws.close(1008, "Expected hello message")
                return

            role = msg.get("role", "audience")

            if role == "presenter":
                if pres.presenter_ws is not None:
                    # Already have a presenter — reject
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "A presenter is already connected",
                    }))
                    await ws.close(1008, "Presenter already connected")
                    return
                pres.presenter_ws = ws
                is_presenter = True
            else:
                pres.audience_clients.append(ws)

            # Handle recording/export params (only from first connection)
            auto_step = msg.get("auto_step")
            if auto_step is not None:
                pres.auto_step = float(auto_step)
            slide_delay = msg.get("slide_delay")
            if slide_delay is not None:
                pres.slide_delay = float(slide_delay)
            if msg.get("instant_sleep"):
                pres.instant_sleep = True

            # Navigate to the requested slide if no slide task is running
            requested_slide = msg.get("slide", 0)
            slide_idle = pres.slide_task is None or pres.slide_task.done()

            if app.state.deck and slide_idle:
                total = len(app.state.deck.slides)
                pres.current_slide = max(0, min(requested_slide, total - 1))
                await asyncio.sleep(0.05)
                pres.slide_task = asyncio.create_task(
                    _run_slide(app, pres)
                )
            else:
                # Session already running — send current state to new client
                if app.state.deck:
                    total = len(app.state.deck.slides)
                    await ws.send_text(json.dumps({
                        "type": "slide",
                        "index": pres.current_slide,
                        "total": total,
                    }))

            # Message loop
            while True:
                data = await ws.receive_text()
                msg = json.loads(data)
                if msg["type"] == "ack":
                    event = pres.pending_acks.pop(msg["id"], None)
                    if event:
                        event.set()
                elif msg["type"] == "keypress":
                    # Audience keypresses ignored when presenter is connected
                    if is_presenter or pres.presenter_ws is None:
                        await _handle_keypress(app, pres, msg["key"])

        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        finally:
            if is_presenter:
                pres.presenter_ws = None
            else:
                if ws in pres.audience_clients:
                    pres.audience_clients.remove(ws)
            # If no clients left, cancel the slide task
            if not pres.has_clients:
                pres.cancel_slide()

    return app


async def _run_slide(app: FastAPI, pres: Presentation) -> None:
    """Run a slide function for the shared presentation."""
    deck = app.state.deck
    index = pres.current_slide
    if not deck or index >= len(deck.slides):
        return
    try:
        await pres.send({"type": "clear"})
        await pres.send({"type": "slide", "index": index, "total": len(deck.slides)})

        slide_fn = deck.slides[index]

        # Send presenter notes (docstring rendered as markdown)
        notes_html = ""
        if slide_fn.func.__doc__:
            import textwrap
            import markdown
            notes_html = markdown.markdown(
                textwrap.dedent(slide_fn.func.__doc__).strip(),
                extensions=["fenced_code", "tables"],
            )
        await pres.send({"type": "notes", "html": notes_html})

        # Send next slide preview
        if index < len(deck.slides) - 1:
            next_fn = deck.slides[index + 1]
            next_excerpt = ""
            if next_fn.func.__doc__:
                import textwrap
                lines = textwrap.dedent(next_fn.func.__doc__).strip().split("\n")
                para = []
                for line in lines:
                    if line.strip() == "" and para:
                        break
                    if line.strip():
                        para.append(line.strip())
                next_excerpt = " ".join(para)
            await pres.send({"type": "next_preview", "title": next_fn.name, "excerpt": next_excerpt})
        else:
            await pres.send({"type": "next_preview", "title": None, "excerpt": ""})

        # Execute the slide body
        from auditorium.slide import SlideContext
        ctx = SlideContext(pres)
        await slide_fn.func(ctx)

        # Signal that the slide function has finished (for exporters)
        await pres.send({"type": "slide_complete", "index": index})

        # Auto-advance in recording mode
        if pres.auto_step is not None:
            await asyncio.sleep(pres.slide_delay)
            if index < len(deck.slides) - 1:
                pres.current_slide = index + 1
                pres.slide_task = asyncio.create_task(_run_slide(app, pres))
                return
            await pres.send({"type": "finished"})
    except (asyncio.CancelledError, Exception):
        pass


async def _handle_keypress(app: FastAPI, pres: Presentation, key: str) -> None:
    """Handle navigation keypress for the shared presentation."""
    deck = app.state.deck
    if not deck:
        return

    if key in ("ArrowRight", " "):
        if pres.step_event is not None:
            pres.step_event.set()
            pres.step_event = None
        else:
            await _go_to_slide(app, pres, pres.current_slide + 1)
    elif key == "PageDown":
        pres.cancel_slide()
        await _go_to_slide(app, pres, pres.current_slide + 1)
    elif key == "ArrowLeft":
        pres.cancel_slide()
        await _go_to_slide(app, pres, pres.current_slide - 1)
    elif key == "r":
        pres.cancel_slide()
        await _go_to_slide(app, pres, pres.current_slide)
    elif key.isdigit():
        pres.numeric_buffer += key
    elif key == "Enter" and pres.numeric_buffer:
        target = int(pres.numeric_buffer) - 1
        pres.numeric_buffer = ""
        pres.cancel_slide()
        await _go_to_slide(app, pres, target)


async def _go_to_slide(app: FastAPI, pres: Presentation, index: int) -> None:
    """Navigate the presentation to a specific slide index."""
    deck = app.state.deck
    if not deck:
        return
    index = max(0, min(index, len(deck.slides) - 1))
    pres.current_slide = index
    pres.cancel_slide()
    pres.slide_task = asyncio.create_task(_run_slide(app, pres))


async def reload_deck(app: FastAPI, new_deck) -> None:
    """Hot-reload: swap the deck and restart the presentation."""
    app.state.deck = new_deck
    pres = app.state.presentation
    total = len(new_deck.slides)
    pres.cancel_slide()
    pres.current_slide = max(0, min(pres.current_slide, total - 1))
    await pres.send({"type": "reload", "slide": pres.current_slide})
    await asyncio.sleep(0.05)
    pres.slide_task = asyncio.create_task(_run_slide(app, pres))
