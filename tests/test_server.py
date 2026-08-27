import inspect

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
