from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from auditorium.compile import compile_deck

if TYPE_CHECKING:
    from auditorium.deck import Deck

STATIC_DIR = Path(__file__).parent / "static"


@dataclass
class Presentation:
    """Connected clients for one presentation. Playback happens in the browser."""

    audience_clients: list[WebSocket] = field(default_factory=list)
    presenter_ws: WebSocket | None = None

    async def send(self, message: dict) -> None:
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

    @property
    def has_clients(self) -> bool:
        return bool(self.audience_clients) or self.presenter_ws is not None


def create_app(deck: Deck | None = None, presenter_mode: bool = False) -> FastAPI:
    app = FastAPI()
    app.state.deck = deck
    app.state.presenter_mode = presenter_mode
    # In presenter mode: one shared Presentation for all tabs
    # In independent mode: one Presentation per tab, stored in a dict
    app.state.shared_pres = Presentation() if presenter_mode else None
    app.state.sessions: dict[str, Presentation] = {}

    @app.on_event("startup")
    async def _capture_loop() -> None:
        app.state.loop = asyncio.get_running_loop()

    @app.on_event("shutdown")
    async def _cleanup() -> None:
        app.state.sessions.clear()

    @app.get("/")
    async def index() -> HTMLResponse:
        html = (STATIC_DIR / "index.html").read_text()
        overrides = deck.theme_style_block() if deck else ""
        html = html.replace("<!--AUDITORIUM_THEME_OVERRIDES-->", overrides)
        return HTMLResponse(html)

    @app.get("/presenter")
    async def presenter_page() -> HTMLResponse:
        if not app.state.presenter_mode:
            return HTMLResponse("Presenter mode not enabled. Start with --presenter.", status_code=403)
        html = (STATIC_DIR / "presenter.html").read_text()
        return HTMLResponse(html)

    @app.get("/timeline.json")
    async def timeline_json() -> JSONResponse:
        if app.state.deck is None:
            return JSONResponse({"version": 1, "meta": {}, "nodes": [],
                                 "ops": [], "tracks": [], "beats": [], "audio": []})
        timeline = await compile_deck(app.state.deck)
        return JSONResponse(timeline.to_dict())

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws.accept()

        try:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg.get("type") != "hello":
                await ws.close(1008, "Expected hello message")
                return

            role = msg.get("role", "audience")

            if app.state.presenter_mode:
                await _handle_shared_session(app, ws, msg, role)
            else:
                if role == "presenter":
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Presenter mode not enabled. Start server with --presenter.",
                    }))
                    await ws.close(1008, "Presenter mode not enabled")
                    return
                await _handle_independent_session(app, ws, msg)

        except (WebSocketDisconnect, asyncio.CancelledError):
            pass

    return app


async def _handle_independent_session(app: FastAPI, ws: WebSocket, hello: dict) -> None:
    """Each tab gets its own Presentation (independent mode)."""
    session_id = str(uuid.uuid4())
    pres = Presentation()
    pres.audience_clients.append(ws)
    app.state.sessions[session_id] = pres

    try:
        while True:
            await ws.receive_text()  # drained; navigation is client-side
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        pres.audience_clients.clear()
        app.state.sessions.pop(session_id, None)


async def _handle_shared_session(app: FastAPI, ws: WebSocket, hello: dict, role: str) -> None:
    """All tabs share one Presentation (presenter mode)."""
    pres = app.state.shared_pres
    is_presenter = False

    if role == "presenter":
        if pres.presenter_ws is not None:
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

    try:
        while True:
            await ws.receive_text()  # drained; navigation is client-side
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        if is_presenter:
            pres.presenter_ws = None
        else:
            if ws in pres.audience_clients:
                pres.audience_clients.remove(ws)


async def reload_deck(app: FastAPI, new_deck) -> None:
    """Hot-reload: swap the deck and tell clients to refetch the timeline."""
    app.state.deck = new_deck
    all_pres = list(app.state.sessions.values())
    if app.state.shared_pres:
        all_pres.append(app.state.shared_pres)
    for pres in all_pres:
        await pres.send({"type": "reload"})
