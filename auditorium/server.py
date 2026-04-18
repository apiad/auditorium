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
class Session:
    """Per-client session holding independent slide state."""

    ws: WebSocket
    slide_task: asyncio.Task | None = None
    current_slide: int = 0
    step_event: asyncio.Event | None = None
    numeric_buffer: str = ""
    pending_acks: dict[str, asyncio.Event] = field(default_factory=dict)
    auto_step: float | None = None
    slide_delay: float = 3.0

    async def send(self, message: dict) -> None:
        """Send a JSON message to this session's client."""
        try:
            await self.ws.send_text(json.dumps(message))
        except Exception:
            pass

    async def send_mutation(self, mutation: dict) -> None:
        """Send a mutation and wait for acknowledgment."""
        mutation_id = str(uuid.uuid4())
        mutation["id"] = mutation_id
        mutation["type"] = "mutation"
        event = asyncio.Event()
        self.pending_acks[mutation_id] = event
        await self.send(mutation)
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


def create_app(deck: Deck | None = None) -> FastAPI:
    app = FastAPI()
    app.state.deck = deck
    app.state.sessions: dict[str, Session] = {}

    @app.on_event("startup")
    async def _capture_loop() -> None:
        app.state.loop = asyncio.get_running_loop()

    @app.on_event("shutdown")
    async def _cleanup_sessions() -> None:
        for session in list(app.state.sessions.values()):
            session.cancel_slide()
        app.state.sessions.clear()

    @app.get("/")
    async def index() -> HTMLResponse:
        html = (STATIC_DIR / "index.html").read_text()
        return HTMLResponse(html)

    @app.get("/presenter")
    async def presenter() -> HTMLResponse:
        html = (STATIC_DIR / "presenter.html").read_text()
        return HTMLResponse(html)

    # Serve all static assets (CSS, JS, fonts, vendor libs)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        session_id = str(uuid.uuid4())
        session = Session(ws=ws)
        app.state.sessions[session_id] = session
        try:
            # Wait for the client's hello message with its current slide
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "hello":
                session.current_slide = msg.get("slide", 0)
                auto_step = msg.get("auto_step")
                if auto_step is not None:
                    session.auto_step = float(auto_step)
                slide_delay = msg.get("slide_delay")
                if slide_delay is not None:
                    session.slide_delay = float(slide_delay)

            # Start the slide for this session
            if app.state.deck:
                # Clamp to valid range
                total = len(app.state.deck.slides)
                session.current_slide = max(0, min(session.current_slide, total - 1))
                await asyncio.sleep(0.05)
                session.slide_task = asyncio.create_task(
                    _run_slide(app, session)
                )

            # Message loop
            while True:
                data = await ws.receive_text()
                msg = json.loads(data)
                if msg["type"] == "ack":
                    event = session.pending_acks.pop(msg["id"], None)
                    if event:
                        event.set()
                elif msg["type"] == "keypress":
                    await _handle_keypress(app, session, msg["key"])
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        finally:
            session.cancel_slide()
            app.state.sessions.pop(session_id, None)

    return app


async def _run_slide(app: FastAPI, session: Session) -> None:
    """Run a slide function for a specific session."""
    deck = app.state.deck
    index = session.current_slide
    if not deck or index >= len(deck.slides):
        return
    try:
        await session.send({"type": "clear"})
        await session.send({"type": "slide", "index": index, "total": len(deck.slides)})

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
        await session.send({"type": "notes", "html": notes_html})

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
            await session.send({"type": "next_preview", "title": next_fn.name, "excerpt": next_excerpt})
        else:
            await session.send({"type": "next_preview", "title": None, "excerpt": ""})

        # Execute the slide body (docstring is NOT rendered as content)
        from auditorium.slide import SlideContext
        ctx = SlideContext(session)
        await slide_fn.func(ctx)

        # Auto-advance in recording mode
        if session.auto_step is not None:
            await asyncio.sleep(session.slide_delay)
            if index < len(deck.slides) - 1:
                session.current_slide = index + 1
                session.slide_task = asyncio.create_task(_run_slide(app, session))
                return
            await session.send({"type": "finished"})
    except (asyncio.CancelledError, Exception):
        pass


async def _handle_keypress(app: FastAPI, session: Session, key: str) -> None:
    """Handle navigation keypress for a specific session."""
    deck = app.state.deck
    if not deck:
        return

    if key in ("ArrowRight", " "):
        if session.step_event is not None:
            session.step_event.set()
            session.step_event = None
        else:
            await _go_to_slide(app, session, session.current_slide + 1)
    elif key == "PageDown":
        session.cancel_slide()
        await _go_to_slide(app, session, session.current_slide + 1)
    elif key == "ArrowLeft":
        session.cancel_slide()
        await _go_to_slide(app, session, session.current_slide - 1)
    elif key == "r":
        session.cancel_slide()
        await _go_to_slide(app, session, session.current_slide)
    elif key.isdigit():
        session.numeric_buffer += key
    elif key == "Enter" and session.numeric_buffer:
        target = int(session.numeric_buffer) - 1
        session.numeric_buffer = ""
        session.cancel_slide()
        await _go_to_slide(app, session, target)


async def _go_to_slide(app: FastAPI, session: Session, index: int) -> None:
    """Navigate a session to a specific slide index."""
    deck = app.state.deck
    if not deck:
        return
    index = max(0, min(index, len(deck.slides) - 1))
    session.current_slide = index
    session.cancel_slide()
    session.slide_task = asyncio.create_task(_run_slide(app, session))


async def reload_deck(app: FastAPI, new_deck) -> None:
    """Hot-reload: swap the deck and restart all sessions at their current slide."""
    app.state.deck = new_deck
    total = len(new_deck.slides)
    for session in list(app.state.sessions.values()):
        session.cancel_slide()
        session.current_slide = max(0, min(session.current_slide, total - 1))
        await session.send({"type": "reload", "slide": session.current_slide})
        await asyncio.sleep(0.05)
        session.slide_task = asyncio.create_task(_run_slide(app, session))
