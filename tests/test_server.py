import inspect

import anyio
import pytest
from fastapi.testclient import TestClient

from auditorium import server
from auditorium.deck import Deck


def make_deck():
    deck = Deck("Served")

    @deck.scene
    async def intro(s):
        h = await s.show("<p>hi</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)

    return deck


def test_timeline_endpoint_returns_the_compiled_timeline():
    client = TestClient(server.create_app(make_deck()))
    body = client.get("/timeline.json").json()
    assert body["meta"]["title"] == "Served"
    assert body["meta"]["duration_ms"] == 500
    assert len(body["nodes"]) == 1


def test_index_still_serves_the_shell_with_theme_overrides():
    client = TestClient(server.create_app(make_deck()))
    html = client.get("/").text
    assert "<!--AUDITORIUM_THEME_OVERRIDES-->" not in html
    assert "slide-root" in html


def test_the_ack_protocol_is_gone():
    src = inspect.getsource(server)
    assert "pending_acks" not in src
    assert "send_mutation" not in src


def _hello(ws, role="audience"):
    """Send the opening hello and return the server's ack."""
    ws.send_json({"type": "hello", "role": role})
    return ws.receive_json()


def test_hello_ack_reports_presenter_mode():
    client = TestClient(server.create_app(make_deck(), presenter_mode=True))
    with client.websocket_connect("/ws") as ws:
        assert _hello(ws)["presenter_mode"] is True

    plain = TestClient(server.create_app(make_deck()))
    with plain.websocket_connect("/ws") as ws:
        assert _hello(ws)["presenter_mode"] is False


def test_a_presenter_command_reaches_every_audience_client():
    client = TestClient(server.create_app(make_deck(), presenter_mode=True))
    with client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        _hello(a)
        _hello(b)
        with client.websocket_connect("/ws") as p:
            _hello(p, role="presenter")
            p.send_json({"type": "cmd", "cmd": "seek", "t": 1200})
            for aud in (a, b):
                msg = aud.receive_json()
                assert (msg["type"], msg["cmd"], msg["t"]) == ("cmd", "seek", 1200)


def test_a_command_is_not_echoed_back_to_the_presenter():
    """An echo would make the presenter seek twice, and often backward.

    A backward seek resets and replays the whole timeline (D5), so an echo
    is not a cosmetic bug -- it is a visible stutter mid-talk.
    """
    client = TestClient(server.create_app(make_deck(), presenter_mode=True))
    with client.websocket_connect("/ws") as a:
        _hello(a)
        with client.websocket_connect("/ws") as p:
            _hello(p, role="presenter")
            p.send_json({"type": "cmd", "cmd": "seek", "t": 900})
            assert a.receive_json()["t"] == 900
            # Round-trip a second command through the audience to prove the
            # presenter's queue stayed empty rather than merely being slow.
            p.send_json({"type": "cmd", "cmd": "seek", "t": 950})
            assert a.receive_json()["t"] == 950
            # Reaching into starlette's receive stream on purpose: the
            # public receive() blocks, and a blocking call cannot express
            # "nothing arrived".
            with pytest.raises(anyio.WouldBlock):
                p._send_rx.receive_nowait()


def test_an_audience_command_is_ignored():
    """Otherwise any tab in the room could drive the talk."""
    client = TestClient(server.create_app(make_deck(), presenter_mode=True))
    with client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        _hello(a)
        _hello(b)
        a.send_json({"type": "cmd", "cmd": "seek", "t": 4200})
        with client.websocket_connect("/ws") as p:
            _hello(p, role="presenter")
            p.send_json({"type": "cmd", "cmd": "seek", "t": 7})
            # b's first message is the presenter's, not a's -- a's was dropped.
            assert b.receive_json()["t"] == 7


def test_a_malformed_frame_does_not_close_the_presentation():
    client = TestClient(server.create_app(make_deck(), presenter_mode=True))
    with client.websocket_connect("/ws") as a:
        _hello(a)
        with client.websocket_connect("/ws") as p:
            _hello(p, role="presenter")
            p.send_text("{not json")
            p.send_json({"type": "cmd", "cmd": "seek", "t": 33})
            assert a.receive_json()["t"] == 33
