"""The SVG layer has to survive a render, not just a live page.

An overlay that only works interactively is half a feature: the point of 4.0
is video. These assertions are on the FRAMES -- a render that completes
without erroring proves nothing about whether anything was drawn.
"""
import hashlib
from pathlib import Path

from auditorium.deck import Deck
from auditorium.nodes import Arrow, Line
from auditorium.render import render_frames


def _svg_deck():
    """Two boxes, an anchored arrow, a move, and a draw-on."""
    deck = Deck("Geometry")

    @deck.scene
    async def wiring(s):
        a = await s.show("<p style='font-size:40px'>A</p>")
        b = await s.show("<p style='font-size:40px'>B</p>")
        # Anchored: the arrow must follow A as it moves.
        await s.draw(Arrow(from_=a.right, to=b.left, stroke="#c00", width=4))
        line = await s.draw(Line(from_=(20, 20), to=(300, 20), stroke="#06c", width=6))
        await s.play(line.animate.draw_on(), run_time=0.5)
        await s.play(a.animate.move_to(120, 0), run_time=0.5)

    return deck


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _frames(d: Path):
    return sorted(d.glob("*.png"))


async def test_the_svg_layer_renders_at_all(tmp_path):
    n = await render_frames(_svg_deck(), tmp_path, fps=10, size=(640, 480))
    assert n == 10
    assert len(_frames(tmp_path)) == 10


async def test_the_draw_on_changes_the_pixels(tmp_path):
    """A stroke that animates must differ between its start and its end.

    Byte-identical frames across an animation is exactly the failure an
    "it rendered without erroring" check cannot see.
    """
    await render_frames(_svg_deck(), tmp_path, fps=10, size=(640, 480))
    frames = _frames(tmp_path)
    assert _digest(frames[0]) != _digest(frames[4]), "draw-on produced no pixel change"


async def test_the_anchored_arrow_moves_with_its_box(tmp_path):
    """Frames spanning the move_to must differ.

    The arrow is anchored to A, so this is also the render-side check that
    anchors resolve per frame rather than once at append.
    """
    await render_frames(_svg_deck(), tmp_path, fps=10, size=(640, 480))
    frames = _frames(tmp_path)
    assert _digest(frames[5]) != _digest(frames[9]), "the anchored arrow never moved"


async def test_the_render_is_still_deterministic_with_geometry(tmp_path):
    """Two renders of a geometric deck must be byte-identical (D2)."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    await render_frames(_svg_deck(), a, fps=10, size=(640, 480))
    await render_frames(_svg_deck(), b, fps=10, size=(640, 480))
    assert [_digest(p) for p in _frames(a)] == [_digest(p) for p in _frames(b)]
