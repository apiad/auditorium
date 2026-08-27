from pathlib import Path

import pytest

from auditorium.cli import _load_deck
from auditorium.compile import compile_deck

EXAMPLES = Path(__file__).parent.parent / "examples"


def example_decks():
    return sorted(EXAMPLES.glob("*.py")) + sorted(EXAMPLES.glob("showcase/*.py"))


@pytest.mark.parametrize("path", example_decks(), ids=lambda p: p.name)
async def test_every_example_deck_compiles(path):
    """Every shipped deck must survive the move to the scene engine."""
    try:
        deck = _load_deck(path)
    except ModuleNotFoundError as exc:
        # Skip, do not pass: some examples need the `examples` extra, and a
        # silent pass here would hide a genuinely broken deck on any machine
        # that happens not to have the optional dependency installed.
        pytest.skip(f"optional dependency not installed: {exc.name}")
    timeline = await compile_deck(deck)
    assert timeline.duration_ms >= 0
    assert timeline.ops, f"{path.name} compiled to an empty timeline"


async def test_the_demo_actually_animates():
    """demo.py is the living documentation, and it has to MOVE.

    The deck it replaced was 25 shim slides of step() reveals and 4 scenes:
    on screen it was a slideshow that faded, which is the opposite of what
    4.0 is for. These assertions are about motion specifically, so the demo
    cannot quietly decay back into a bullet tour.
    """
    source = (EXAMPLES / "demo.py").read_text()
    assert "@deck.slide" not in source, "the demo is scenes, not slides"
    assert "@deck.scene" in source
    for primitive in ("s.play(", "move_to(", "draw_on()", "lag=", "s.draw(", "ease="):
        assert primitive in source, f"the demo no longer exercises {primitive}"


async def test_the_demo_is_mostly_motion():
    """More animation calls than static shows -- a floor, not a formality."""
    source = (EXAMPLES / "demo.py").read_text()
    assert source.count("animate.") >= 12
