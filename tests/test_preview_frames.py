"""The preview's frame readout must agree with what a render produces.

`render_schedule` (Python) and `player.renderFrameCount` (JS) are two
implementations of one rule: timeline frames plus a dwell per beat. Two
implementations drift, and this drift would be invisible -- the preview would
simply quote a number the rendered file does not have. So the agreement is
asserted mechanically rather than trusted.
"""
import json
from pathlib import Path

import pytest

from auditorium.compile import compile_deck
from auditorium.deck import Deck
from auditorium.render import frame_count, render_schedule

CLIENT = Path(__file__).parent.parent / "auditorium" / "static" / "client.js"


def _slide_deck():
    """A shim deck: every beat holds 1.5s, so render frames exceed timeline frames."""
    deck = Deck("Slides")

    @deck.slide
    async def a(ctx):
        await ctx.title("one")
        await ctx.step()
        await ctx.md("more")

    @deck.slide
    async def b(ctx):
        await ctx.title("two")
        await ctx.step()
        await ctx.md("more")

    return deck


def _scene_deck():
    """A scene deck: beats hold nothing, so the two counts coincide."""
    deck = Deck("Scenes")

    @deck.scene
    async def s(ctx):
        h = await ctx.show("<p>x</p>")
        await ctx.play(h.animate.fade_in(), run_time=0.5)
        await ctx.beat()
        await ctx.wait(1.0)

    return deck


async def _js_counts(page, timeline_dict, fps):
    """Load client.js in a real browser and ask the player for its counts."""
    src = CLIENT.read_text()
    await page.set_content("<!DOCTYPE html><html><body></body></html>")
    await page.add_script_tag(content=src.replace("export function", "function"))
    return await page.evaluate(
        """([tl, fps]) => {
            const engine = { load() {}, seek() {}, get currentTime() { return 0; } };
            const p = createPlayer({ engine });
            tl.meta = Object.assign({}, tl.meta, { fps });
            p.load(tl);
            const at = tl.beats.map(b => p.renderFrameOf(b.t));
            return { count: p.renderFrameCount(), at };
        }""",
        [json.loads(json.dumps(timeline_dict)), fps],
    )


@pytest.mark.parametrize("fps", [24, 30, 60])
async def test_the_preview_frame_count_matches_a_render_of_a_slide_deck(browser_page, fps):
    tl = await compile_deck(_slide_deck())
    js = await _js_counts(browser_page, tl.to_dict(), fps)
    assert js["count"] == frame_count(tl, fps)
    # And the difference is real, not a coincidence of both being timeline
    # frames: a shim deck's beats each add 1.5s of dwell.
    assert js["count"] > int(tl.duration_ms * fps / 1000)


@pytest.mark.parametrize("fps", [24, 30, 60])
async def test_the_two_counts_coincide_for_a_scene_deck(browser_page, fps):
    tl = await compile_deck(_scene_deck())
    js = await _js_counts(browser_page, tl.to_dict(), fps)
    assert js["count"] == frame_count(tl, fps)


async def test_every_frame_time_maps_to_the_frame_that_shows_it(browser_page):
    """Not just the total: the mapping has to point at the right frame.

    Stated over frame times rather than beat times, because a beat's dwell is
    emitted on the first frame at-or-after it -- a beat at t=1ms is dwelt on
    by the frame at t=33ms, so "the frame index of the beat's millisecond" is
    not a well-defined thing to assert.
    """
    fps = 30
    tl = await compile_deck(_slide_deck())
    schedule = render_schedule(tl, fps)
    src = CLIENT.read_text()
    await browser_page.set_content("<!DOCTYPE html><html><body></body></html>")
    await browser_page.add_script_tag(content=src.replace("export function", "function"))
    reported = await browser_page.evaluate(
        """([tl, fps]) => {
            const engine = { load() {}, seek() {}, get currentTime() { return 0; } };
            const p = createPlayer({ engine });
            tl.meta = Object.assign({}, tl.meta, { fps });
            p.load(tl);
            const n = Math.trunc(p.duration * fps / 1000);
            const out = [];
            for (let i = 0; i < n; i++) out.push(p.renderFrameOf(Math.trunc(i * 1000 / fps)));
            return out;
        }""",
        [json.loads(json.dumps(tl.to_dict())), fps],
    )
    assert len(reported) > 1
    for i, index in enumerate(reported):
        assert schedule[index] == int(i * 1000 / fps)
