import shutil
import subprocess

import pytest

from auditorium.compile import compile_deck
from auditorium.deck import Deck
from auditorium.render import render_video

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


@pytest.fixture
def tone(tmp_path):
    """A 3-second sine wave, generated rather than committed as a fixture."""
    path = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         str(path)],
        capture_output=True, check=True,
    )
    return path


def _deck(tone=None):
    deck = Deck("Audio")
    if tone is not None:
        deck.audio(tone)

    @deck.scene
    async def one(s):
        h = await s.show("<p>x</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)

    return deck


async def test_declared_audio_reaches_the_timeline(tone):
    tl = await compile_deck(_deck(tone))
    assert tl.audio and tl.audio[0]["at"] == 0.0


async def test_rendered_video_has_an_audio_stream(tmp_path, tone):
    out = await render_video(_deck(tone), tmp_path / "o.mp4", fps=10, size=(320, 240))
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True,
    )
    assert "aac" in probe.stdout


async def test_audio_is_truncated_to_the_video_length(tmp_path, tone):
    """The tone is 3s; the timeline is 0.5s. -shortest must win."""
    out = await render_video(_deck(tone), tmp_path / "o.mp4", fps=10, size=(320, 240))
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(out)],
        capture_output=True, text=True,
    )
    assert float(dur.stdout.strip()) < 1.5


async def test_a_deck_without_audio_still_renders(tmp_path):
    out = await render_video(_deck(), tmp_path / "o.mp4", fps=10, size=(320, 240))
    assert out.exists()
