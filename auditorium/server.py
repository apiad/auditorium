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
    # The last command relayed, replayed to audience tabs as they join. The
    # server still holds no position of its own -- this is a cached message,
    # not state it computes. Without it a tab that drops for a second (the
    # client auto-reconnects, so that is routine) rejoins at the start of the
    # deck while the room is on scene three.
    last_cmd: dict | None = None

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

    async def send_to_audience(self, message: dict) -> None:
        """Fan a command out to audience tabs only.

        Deliberately not ``send()``: echoing a command back to the presenter
        that issued it would make it seek twice, and the second seek would be
        backward often enough to trigger a full reset-and-replay mid-talk.
        """
        data = json.dumps(message)
        for ws in list(self.audience_clients):
            try:
                await ws.send_text(data)
            except Exception:
                self.audience_clients.remove(ws)

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
        # Injected into the shell rather than sent over the socket, because
        # the audience has to decide whether to autoplay at load time. Waiting
        # for hello_ack would race it: in shared mode an autoplaying audience
        # and a presenter starting at zero drift apart immediately.
        mode = "true" if app.state.presenter_mode else "false"
        html = html.replace(
            "<!--AUDITORIUM_MODE-->",
            f'<meta name="auditorium-presenter-mode" content="{mode}">',
        )
        return HTMLResponse(html)

    @app.get("/preview")
    async def preview_page() -> HTMLResponse:
        """The authoring surface. Needs no mode flag, unlike /presenter:
        previewing is never shared, so there is no session it can be wrong for.
        """
        html = (STATIC_DIR / "preview.html").read_text()
        overrides = deck.theme_style_block() if deck else ""
        return HTMLResponse(html.replace("<!--AUDITORIUM_THEME_OVERRIDES-->", overrides))

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
    await ws.send_text(json.dumps({"type": "hello_ack", "presenter_mode": False}))

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

    await ws.send_text(json.dumps({"type": "hello_ack", "presenter_mode": True}))
    if not is_presenter and pres.last_cmd is not None:
        # Catch a joining or reconnecting tab up to where the room is. Sent as
        # a seek rather than the original command: replaying a playTo would
        # re-animate a segment the audience already watched.
        await ws.send_text(json.dumps(
            {"type": "cmd", "cmd": "seek", "t": pres.last_cmd.get("t", 0)}
        ))

    try:
        while True:
            raw = await ws.receive_text()
            # The server relays intent and holds no position of its own. Only
            # the presenter may drive: without this check any audience tab
            # could navigate the talk, and "audience keyboards are locked"
            # would be enforced by nothing but the audience's good manners.
            if not is_presenter:
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                continue  # a bad frame from one tab must not end the talk
            if isinstance(msg, dict) and msg.get("type") == "cmd":
                # A playTo caches as its destination: a late tab should arrive
                # where the room is, not replay the animation getting there.
                pres.last_cmd = {"cmd": "seek", "t": msg.get("to", msg.get("t", 0))}
                await pres.send_to_audience(msg)
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
