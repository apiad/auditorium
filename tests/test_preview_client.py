"""The preview client: the authoring surface (D8).

Scrubber, frame stepping, loop-a-range, and a hot reload that holds position.
Every assertion here goes through the real page in a real browser, because the
whole value of a preview is that it shows what the renderer will produce.
"""
import asyncio
import threading

import pytest_asyncio
import uvicorn

from auditorium.deck import Deck
from auditorium.server import create_app


def _deck():
    deck = Deck("Preview")

    @deck.scene
    async def one(s):
        h = await s.show("<p id='mover'>first</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)
        await s.play(h.animate.move_to(300, 0), run_time=1.0)
        await s.beat()
        h2 = await s.show("<p>second</p>")
        await s.play(h2.animate.fade_in(), run_time=0.5)

    return deck


@pytest_asyncio.fixture
async def live_server():
    """A uvicorn server on an ephemeral port, with a bounded startup wait.

    Same shape as tests/test_present_client.py, and for the same two reasons:
    a fixed port makes the second test in the file hang on a socket the first
    has not released, and an unbounded wait turns a startup failure into a
    hang rather than a red test.
    """
    config = uvicorn.Config(
        create_app(_deck()), host="127.0.0.1", port=0, log_level="warning"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = 10.0
    while not server.started:
        await asyncio.sleep(0.05)
        deadline -= 0.05
        if deadline <= 0:
            server.should_exit = True
            raise RuntimeError("uvicorn did not start within 10s")

    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


async def _ready(page, url):
    """Load the preview and wait for it to come alive.

    Bounded on purpose: unbounded, a 404 or a script error becomes a hung
    suite rather than a red test, and a hang is strictly harder to diagnose.
    """
    await page.goto(url + "/preview")
    await page.wait_for_function(
        "() => window.__auditorium_ready === true", timeout=10000
    )


async def _state(page):
    return await page.evaluate("() => window.__auditorium_preview.state()")


async def test_the_scrubber_spans_the_whole_timeline(browser_page, live_server):
    await _ready(browser_page, live_server)
    span = await browser_page.evaluate(
        "() => { const s = document.getElementById('scrub');"
        " return [Number(s.min), Number(s.max)]; }"
    )
    duration = await browser_page.evaluate("() => window.__auditorium_duration")
    assert span == [0, duration]
    assert duration > 0


async def test_the_preview_opens_paused_at_zero(browser_page, live_server):
    """An authoring surface that starts playing fights the author."""
    await _ready(browser_page, live_server)
    state = await _state(browser_page)
    assert state["t"] == 0
    assert state["playing"] is False


async def test_dragging_the_scrubber_seeks_the_stage(browser_page, live_server):
    await _ready(browser_page, live_server)
    await browser_page.evaluate(
        "() => { const s = document.getElementById('scrub');"
        " s.value = 700; s.dispatchEvent(new Event('input')); }"
    )
    assert await browser_page.evaluate("() => window.AuditoriumEngine.currentTime") == 700


async def test_the_frame_readout_matches_the_timeline_position(browser_page, live_server):
    await _ready(browser_page, live_server)
    await browser_page.evaluate(
        "() => { const s = document.getElementById('scrub');"
        " s.value = 1000; s.dispatchEvent(new Event('input')); }"
    )
    state = await _state(browser_page)
    # 1000ms at 30fps is frame 30.
    assert state["frame"] == 30
    assert "30" in await browser_page.text_content("#frame-readout")


async def test_step_forward_advances_exactly_one_frame(browser_page, live_server):
    await _ready(browser_page, live_server)
    await browser_page.keyboard.press("Period")
    await browser_page.keyboard.press("Period")
    state = await _state(browser_page)
    assert state["frame"] == 2
    # Two frames at 30fps is 66ms, not 67: the frame index is authoritative
    # and the time is derived from it, never the other way round.
    assert state["t"] == round(2 * 1000 / 30)


async def test_step_backward_lands_on_the_same_state_as_seeking_there_fresh(
    browser_page, live_server
):
    """The D5 guard at the client level.

    Backward stepping must go through the engine's reset-and-replay. If it
    ever "optimises" into a backward seek, the author is shown a state the
    renderer will never produce -- which breaks D2 at exactly the moment
    they are relying on it.
    """
    await _ready(browser_page, live_server)
    for _ in range(4):
        await browser_page.keyboard.press("Period")
    await browser_page.keyboard.press("Comma")
    stepped = await browser_page.evaluate(
        "() => [document.getElementById('slide-root').innerHTML,"
        " getComputedStyle(document.getElementById('mover')).transform,"
        " getComputedStyle(document.getElementById('mover')).opacity]"
    )
    stepped_t = (await _state(browser_page))["t"]

    await _ready(browser_page, live_server)
    await browser_page.evaluate(
        "(t) => { const s = document.getElementById('scrub');"
        " s.value = t; s.dispatchEvent(new Event('input')); }",
        stepped_t,
    )
    fresh = await browser_page.evaluate(
        "() => [document.getElementById('slide-root').innerHTML,"
        " getComputedStyle(document.getElementById('mover')).transform,"
        " getComputedStyle(document.getElementById('mover')).opacity]"
    )
    assert stepped == fresh


async def test_loop_range_wraps_playback_back_to_the_in_point(browser_page, live_server):
    await _ready(browser_page, live_server)
    await browser_page.evaluate(
        "() => window.__auditorium_preview.setLoop(100, 300)"
    )
    await browser_page.evaluate("() => window.__auditorium_preview.toggleLoop()")
    await browser_page.evaluate("() => window.__auditorium_preview.playPause()")
    await browser_page.wait_for_function(
        "() => window.__auditorium_preview.state().loops >= 2", timeout=10000
    )
    state = await _state(browser_page)
    assert state["t"] <= 300
    assert state["loop"]["enabled"] is True


async def test_hot_reload_holds_the_current_position(browser_page, live_server):
    """Recompiling must not throw the author back to zero.

    The spec left this open; holding t is the answer a pure timeline can
    give. If the edit changed what exists at that instant, the author sees
    the new scene at the old time -- which is the useful behaviour.
    """
    await _ready(browser_page, live_server)
    await browser_page.evaluate(
        "() => { const s = document.getElementById('scrub');"
        " s.value = 900; s.dispatchEvent(new Event('input')); }"
    )
    await browser_page.evaluate("() => window.__auditorium_preview.reload()")
    await browser_page.wait_for_function(
        "() => window.__auditorium_preview.state().reloads === 1", timeout=10000
    )
    assert await browser_page.evaluate("() => window.AuditoriumEngine.currentTime") == 900


async def test_the_preview_route_needs_no_presenter_mode(browser_page, live_server):
    """Previewing is never shared, so there is no mode it can be wrong for."""
    response = await browser_page.goto(live_server + "/preview")
    assert response.status == 200
