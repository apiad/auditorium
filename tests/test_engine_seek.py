import json
from pathlib import Path

import pytest

from auditorium.timeline import Node, Op, Timeline, Track

FIXTURE = Path(__file__).parent / "fixtures" / "engine_harness.html"
ENGINE = Path(__file__).parent.parent / "auditorium" / "static" / "engine.js"


@pytest.fixture
def timeline_dict():
    """A box that fades in over 500ms, then slides 0 -> 500px over 1000ms."""
    tl = Timeline(meta={"title": "fixture"})
    tl.nodes.append(Node(id="n1", layer="dom", html="<div id='box'>box</div>"))
    tl.ops.append(Op(t=0, action="append", node="n1"))
    tl.tracks.append(Track(node="n1", prop="opacity", from_=0, to=1, start=0, end=500))
    tl.tracks.append(
        Track(node="n1", prop="transform.x", from_=0, to=500, start=500, end=1500)
    )
    return tl.to_dict()


async def serve(page, timeline_dict):
    """Load the harness with engine.js and the timeline, without a server."""
    engine_src = ENGINE.read_text()
    html = FIXTURE.read_text().replace(
        '<script type="module">\n    import { AuditoriumEngine } from "/engine.js";\n'
        "    window.AuditoriumEngine = AuditoriumEngine;\n  </script>",
        f"<script type='module'>\n{engine_src}\n"
        "window.AuditoriumEngine = AuditoriumEngine;\n</script>",
    )
    await page.set_content(html)
    await page.evaluate(
        "(tl) => window.AuditoriumEngine.load(tl)", json.loads(json.dumps(timeline_dict))
    )


async def x_of(page, selector="#n1"):
    return await page.evaluate(
        "(sel) => { const el = document.querySelector(sel);"
        " if (!el) return null;"
        " const m = new DOMMatrix(getComputedStyle(el).transform);"
        " return Math.round(m.m41); }",
        selector,
    )


async def opacity_of(page, selector="#n1"):
    return await page.evaluate(
        "(sel) => { const el = document.querySelector(sel);"
        " return el ? parseFloat(getComputedStyle(el).opacity) : null; }",
        selector,
    )


async def test_ops_apply_at_their_time(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    assert await browser_page.evaluate("() => !!document.querySelector('#n1')")


async def test_opacity_interpolates_at_the_midpoint(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(250)")
    assert 0.4 < await opacity_of(browser_page) < 0.6


async def test_a_finished_track_holds_its_end_value(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(1500)")
    assert await opacity_of(browser_page) == pytest.approx(1.0)
    assert await x_of(browser_page) == 500


async def test_a_track_that_has_not_started_holds_its_start_value(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(100)")
    assert await x_of(browser_page) == 0


async def test_seek_drives_pseudo_element_animations(browser_page, timeline_dict):
    """A private registry cannot see ::after. getAnimations() can."""
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(1200)")
    paused = await browser_page.evaluate(
        "() => document.getAnimations().every(a => a.playState === 'paused')"
    )
    assert paused is True
    times = await browser_page.evaluate(
        "() => document.getAnimations().map(a => a.currentTime)"
    )
    assert times and all(t == 1200 for t in times)


async def test_backward_seek_resets_and_replays(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(1500)")
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(250)")
    assert await x_of(browser_page) == 0
    assert 0.4 < await opacity_of(browser_page) < 0.6


async def test_ops_are_not_applied_twice_on_repeated_forward_seeks(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(10)")
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(20)")
    count = await browser_page.evaluate(
        "() => document.querySelectorAll('#slide-root > *').length"
    )
    assert count == 1


async def test_tween_callbacks_receive_the_current_time(browser_page, timeline_dict):
    await serve(browser_page, timeline_dict)
    await browser_page.evaluate(
        "() => { window.__seen = [];"
        " window.AuditoriumEngine.registerTween(t => window.__seen.push(t)); }"
    )
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(300)")
    assert await browser_page.evaluate("() => window.__seen.at(-1)") == 300


async def test_seek_is_path_independent(browser_page, timeline_dict):
    """Capture forward, seek to the end, re-capture. States must match.

    A 'render twice and compare' test cannot catch this — both runs travel
    forward. Seeking is genuinely path-dependent unless backward seeks reset.
    """
    await serve(browser_page, timeline_dict)
    probes = [0, 250, 500, 750, 1000, 1250, 1500]

    forward = []
    for t in probes:
        await browser_page.evaluate("(t) => window.AuditoriumEngine.seek(t)", t)
        forward.append((await opacity_of(browser_page), await x_of(browser_page)))

    await browser_page.evaluate("() => window.AuditoriumEngine.seek(3000)")

    again = []
    for t in probes:
        await browser_page.evaluate("(t) => window.AuditoriumEngine.seek(t)", t)
        again.append((await opacity_of(browser_page), await x_of(browser_page)))

    assert again == forward
