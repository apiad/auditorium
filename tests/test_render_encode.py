import shutil
import subprocess
from pathlib import Path

import pytest

from auditorium.deck import Deck
from auditorium.render import parse_size, render_video

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


def _deck():
    deck = Deck("Video")

    @deck.scene
    async def one(s):
        h = await s.show("<p style='font-size:80px'>HELLO</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)

    return deck


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_name,width,height,nb_read_packets",
         "-count_packets", "-select_streams", "v:0", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def test_size_presets_resolve():
    assert parse_size("1920x1080") == (1920, 1080)
    assert parse_size("vertical") == (1080, 1920)
    assert parse_size("square") == (1080, 1080)


def test_an_unknown_size_is_rejected():
    with pytest.raises(ValueError):
        parse_size("enormous")


async def test_produces_a_playable_mp4(tmp_path):
    out = await render_video(_deck(), tmp_path / "o.mp4", fps=10, size=(320, 240))
    assert out.exists() and out.stat().st_size > 0
    probe = _probe(out)
    assert "h264" in probe
    assert "320,240" in probe


async def test_the_video_has_the_scheduled_frame_count(tmp_path):
    """Asserts on the encoded artifact, not on how many PNGs we wrote."""
    out = await render_video(_deck(), tmp_path / "o.mp4", fps=10, size=(320, 240))
    assert _probe(out).split(",")[-1] == "5"


async def test_two_renders_produce_identical_video_bytes(tmp_path):
    a = await render_video(_deck(), tmp_path / "a.mp4", fps=10, size=(320, 240))
    b = await render_video(_deck(), tmp_path / "b.mp4", fps=10, size=(320, 240))
    assert a.read_bytes() == b.read_bytes()


async def test_png_sequence_format_leaves_frames_on_disk(tmp_path):
    out = await render_video(_deck(), tmp_path / "seq", fps=10, size=(320, 240),
                             fmt="png-sequence")
    assert len(list(Path(out).glob("*.png"))) == 5
