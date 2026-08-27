import asyncio
import threading

import pytest
import pytest_asyncio
import uvicorn

from auditorium.deck import Deck
from auditorium.server import create_app


def _deck():
    deck = Deck("Live")

    @deck.scene
    async def one(s):
        h = await s.show("<p>first</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)
        await s.beat()
        h2 = await s.show("<p>second</p>")
        await s.play(h2.animate.fade_in(), run_time=0.5)

    return deck


@pytest_asyncio.fixture
async def live_server():
    """A uvicorn server on an EPHEMERAL port, with a bounded startup wait.

    Both details are load-bearing. A fixed port makes the second test in the
    file hang forever on `while not server.started`, because the first test's
    socket has not been released yet; and an unbounded wait turns any startup
    failure into a hang rather than a failure, which is strictly harder to
    diagnose than a red test.
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
    await page.goto(url)
    await page.wait_for_function("() => window.__auditorium_ready === true")


async def _settle_at_first_beat(page):
    """Wait for the opening segment to finish playing into the first beat.

    Pressing space mid-playback is a different gesture: it skips to the beat
    rather than past it. Tests that mean "advance from the beat" have to let
    the segment land first, or they race the animation and assert on a state
    the user never sees.
    """
    await page.wait_for_function(
        "() => window.AuditoriumEngine.currentTime >= 500", timeout=10000
    )


async def test_client_loads_the_timeline_and_renders_the_first_scene(
    browser_page, live_server
):
    await _ready(browser_page, live_server)
    await browser_page.wait_for_selector("#slide-root >> text=first")


async def test_space_advances_past_the_beat(browser_page, live_server):
    await _ready(browser_page, live_server)
    await browser_page.wait_for_selector("#slide-root >> text=first")
    await _settle_at_first_beat(browser_page)
    await browser_page.keyboard.press(" ")
    await browser_page.wait_for_selector("#slide-root >> text=second")


async def test_space_during_playback_skips_to_the_beat_not_past_it(
    browser_page, live_server
):
    """Mid-segment space is a skip, not an advance.

    Two distinct gestures share one key, and conflating them would make a
    presenter's first impatient keypress blow through a reveal.
    """
    await _ready(browser_page, live_server)
    await browser_page.keyboard.press(" ")
    await browser_page.wait_for_function(
        "() => window.AuditoriumEngine.currentTime === 500", timeout=10000
    )
    text = await browser_page.evaluate(
        "() => document.getElementById('slide-root').textContent"
    )
    assert "second" not in text


async def test_content_after_the_beat_is_not_visible_at_the_beat(
    browser_page, live_server
):
    """The 1ms bump in beat() has to hold end to end, not just in the compiler.

    If it does not, the reveal is on screen before the keypress meant to
    trigger it, and space appears to do nothing.
    """
    await _ready(browser_page, live_server)
    await _settle_at_first_beat(browser_page)
    text = await browser_page.evaluate(
        "() => document.getElementById('slide-root').textContent"
    )
    assert "first" in text
    assert "second" not in text


async def test_backward_navigation_works(browser_page, live_server):
    """D7 of the 2.0 design rejected this outright. A timeline makes it free."""
    await _ready(browser_page, live_server)
    await _settle_at_first_beat(browser_page)
    await browser_page.keyboard.press(" ")
    await browser_page.wait_for_selector("#slide-root >> text=second")
    await browser_page.keyboard.press("ArrowLeft")
    await browser_page.wait_for_function(
        "() => !document.getElementById('slide-root').textContent.includes('second')",
        timeout=10000,
    )


async def test_math_and_code_are_still_decorated(browser_page, live_server):
    """KaTeX and highlight.js survived the client rewrite.

    They lived inside the deleted script block; losing them would break math
    and code in every deck while the timeline tests all stayed green.
    """
    await _ready(browser_page, live_server)
    hooked = await browser_page.evaluate(
        "() => typeof window.AuditoriumEngine.onAppend === 'function'"
    )
    assert hooked is True
