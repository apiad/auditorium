import hashlib
from pathlib import Path


from auditorium.deck import Deck
from auditorium.render import render_frames


def _deck():
    """A deck that is visible at t=0 AND changes over time.

    Both properties are required, and an earlier version of this fixture could
    not have both: it opened with fade_in(), so frame 0 was legitimately blank
    (opacity 0 — a fade-in correctly starts empty) and the fonts-gate test was
    unsatisfiable. A static element carries frame 0; a second, animated element
    supplies the change.
    """
    deck = Deck("Render")

    @deck.scene
    async def one(s):
        await s.show("<p style='font-size:60px'>STATIC</p>")
        h = await s.show("<p style='font-size:80px'>HELLO</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)
        await s.play(h.animate.move_by(200, 0), run_time=0.5)

    return deck


def _digests(d: Path):
    return [hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.glob("*.png"))]


async def test_renders_the_expected_number_of_frames(tmp_path):
    n = await render_frames(_deck(), tmp_path, fps=10, size=(320, 240))
    assert n == 10
    assert len(list(tmp_path.glob("*.png"))) == 10


async def test_frames_are_not_all_identical(tmp_path):
    """Guards the whole point: if seek() were a no-op every frame would match
    and a frame-count assertion alone would still pass."""
    await render_frames(_deck(), tmp_path, fps=10, size=(320, 240))
    assert len(set(_digests(tmp_path))) > 1


async def test_two_renders_are_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    await render_frames(_deck(), a, fps=10, size=(320, 240))
    await render_frames(_deck(), b, fps=10, size=(320, 240))
    assert _digests(a) == _digests(b)


async def test_frame_zero_is_not_blank(tmp_path):
    """Without a fonts.ready gate exactly one frame is wrong, and it is this one.

    Compared against an empty deck's frame: a solid-colour PNG compresses to
    almost nothing, so a frame with rendered text is several times larger.
    Asserting merely that frame 0 is non-empty would pass on a blank image.
    """
    empty = Deck("Empty")

    @empty.scene
    async def nothing(s):
        await s.wait(1.0)

    blank_dir = tmp_path / "blank"
    real_dir = tmp_path / "real"
    blank_dir.mkdir()
    real_dir.mkdir()
    await render_frames(empty, blank_dir, fps=10, size=(320, 240))
    await render_frames(_deck(), real_dir, fps=10, size=(320, 240))

    blank_size = sorted(blank_dir.glob("*.png"))[0].stat().st_size
    first_size = sorted(real_dir.glob("*.png"))[0].stat().st_size
    assert first_size > blank_size * 2, (
        f"frame 0 ({first_size}B) is close to blank ({blank_size}B) — "
        "content had not rendered when it was captured"
    )


async def test_a_frame_range_renders_only_that_range(tmp_path):
    n = await render_frames(_deck(), tmp_path, fps=10, size=(320, 240),
                            start_frame=3, end_frame=6)
    assert n == 3
    names = sorted(p.name for p in tmp_path.glob("*.png"))
    assert names == ["frame-000003.png", "frame-000004.png", "frame-000005.png"]


async def test_a_range_matches_the_same_frames_of_a_full_render(tmp_path):
    """The claim that makes parallel rendering safe: a worker starting at frame
    N produces exactly what a sequential render produces at frame N."""
    full, part = tmp_path / "full", tmp_path / "part"
    full.mkdir()
    part.mkdir()
    await render_frames(_deck(), full, fps=10, size=(320, 240))
    await render_frames(_deck(), part, fps=10, size=(320, 240),
                        start_frame=4, end_frame=7)
    full_d = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in full.glob("*.png")}
    part_d = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in part.glob("*.png")}
    assert part_d
    for name, digest in part_d.items():
        assert full_d[name] == digest, f"{name} differs between full and ranged render"
