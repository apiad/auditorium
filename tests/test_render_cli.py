import shutil

import pytest
from typer.testing import CliRunner

from auditorium.cli import app

runner = CliRunner()


def test_render_command_exists_and_documents_itself():
    result = runner.invoke(app, ["render", "--help"])
    assert result.exit_code == 0
    for flag in ["--fps", "--size", "--format", "--audio"]:
        assert flag in result.stdout


def test_record_is_gone():
    """record produced nondeterministic screen capture; render replaces it."""
    result = runner.invoke(app, ["record", "--help"])
    assert result.exit_code != 0


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_render_writes_a_file(tmp_path):
    out = tmp_path / "out.mp4"
    result = runner.invoke(app, [
        "render", "examples/demo_deck.py", "-o", str(out),
        "--fps", "5", "--size", "320x240", "--to", "10",
    ])
    assert result.exit_code == 0, result.stdout
    assert out.exists() and out.stat().st_size > 0
