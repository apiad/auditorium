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


async def test_demo_deck_exercises_the_animation_vocabulary():
    """demo_deck.py is living documentation; new primitives must appear in it."""
    source = (EXAMPLES / "demo_deck.py").read_text()
    assert "@deck.scene" in source
    assert ".animate." in source
    assert "s.play(" in source
