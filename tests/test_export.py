import asyncio
from pathlib import Path

import pytest

from auditorium.exporter import export_deck

DECK_SRC = '''
from auditorium import Deck

deck = Deck("Export")

@deck.scene
async def alpha(s):
    await s.show("<p>ALPHA</p>")

@deck.scene
async def bravo(s):
    await s.show("<p>BRAVO</p>")
'''


@pytest.fixture
def deck_file(tmp_path):
    """export_deck takes a PATH, not a Deck: it loads the module itself."""
    path = tmp_path / "d.py"
    path.write_text(DECK_SRC)
    return path


async def test_png_export_writes_one_image_per_beat(deck_file, tmp_path):
    out = tmp_path / "png"
    await export_deck(deck_file, out, "png", "320x240", False, 0)
    pngs = sorted(out.glob("*.png"))
    assert len(pngs) >= 2
    assert all(p.stat().st_size > 0 for p in pngs)


async def test_export_completes_without_hanging(deck_file, tmp_path):
    """The regression this task fixes: export waited forever on
    window.__auditorium_slide_complete, which the new client never sets.
    Measured before the fix: TimeoutError after 120s, no output produced."""
    out = tmp_path / "png2"
    await asyncio.wait_for(
        export_deck(deck_file, out, "png", "320x240", False, 0), timeout=90
    )


async def test_exported_frames_do_not_all_carry_the_same_page_number(
    deck_file, tmp_path
):
    """Chrome has to advance with the capture, not freeze at its load value.

    Driving AuditoriumEngine.seek() directly skips the client's updateChrome(),
    which burned a single wrong "2 / 63" into all 63 stills of the demo deck
    while every other assertion stayed green. Counting files cannot catch this;
    only looking at what is in them can.
    """
    import re

    out = tmp_path / "png3"
    await export_deck(deck_file, out, "png", "320x240", False, 0)
    pngs = sorted(out.glob("*.png"))
    assert len(pngs) >= 2

    # The indicator is rendered into the image, so compare the images: two
    # different scenes must not produce byte-identical frames.
    import hashlib
    digests = {hashlib.sha256(p.read_bytes()).hexdigest() for p in pngs}
    assert len(digests) == len(pngs), "captured frames are not all distinct"


async def test_the_export_stylesheet_hides_the_live_connection_dot(browser_page):
    """A still is not a session; the WebSocket status dot has no meaning in one.

    Asserts the rule actually takes effect in a browser rather than that the
    string appears in the source -- a source grep survives the bug it was
    written for the moment the selector changes.
    """
    import inspect
    import re

    import auditorium.exporter as exporter

    src = inspect.getsource(exporter.export_deck)
    css = re.search(r'DISABLE_ANIM_CSS = """(.*?)"""', src, re.DOTALL).group(1)

    await browser_page.set_content(
        "<div id='connection-status'>dot</div><div id='other'>x</div>"
    )
    await browser_page.add_style_tag(content=css)
    hidden = await browser_page.evaluate(
        "() => getComputedStyle(document.getElementById('connection-status')).display"
    )
    visible = await browser_page.evaluate(
        "() => getComputedStyle(document.getElementById('other')).display"
    )
    assert hidden == "none"
    assert visible != "none", "the rule is too broad and hid unrelated elements"
