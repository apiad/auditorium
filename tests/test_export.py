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
