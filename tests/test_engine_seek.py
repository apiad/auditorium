import json
from pathlib import Path

import pytest

from auditorium.timeline import Node, Op, Timeline, Track

FIXTURE = Path(__file__).parent / "fixtures" / "engine_harness.html"
ENGINE = Path(__file__).parent.parent / "auditorium" / "static" / "engine.js"


@pytest.fixture
def timeline_dict():
    """A box that fades in over 500ms, then slides 0 -> 500px over 1000ms.

    A SECOND node enters at t=1000. That structural op at t>0 is what makes
    the reset observable: with only a t=0 op and fill:both tracks, rendered
    state is a pure function of t, `_applied` saturates, and removing the
    backward-seek reset changes nothing an assertion can see.
    """
    tl = Timeline(meta={"title": "fixture"})
    tl.nodes.append(Node(id="n1", layer="dom", html="<div id='box'>box</div>"))
    tl.ops.append(Op(t=0, action="append", node="n1"))
    tl.tracks.append(Track(node="n1", prop="opacity", from_=0, to=1, start=0, end=500))
    tl.tracks.append(
        Track(node="n1", prop="transform.x", from_=0, to=500, start=500, end=1500)
    )
    tl.nodes.append(Node(id="n2", layer="dom", html="<div id='late'>late</div>"))
    tl.ops.append(Op(t=1000, action="append", node="n2"))
    return tl.to_dict()


async def child_count(page):
    return await page.evaluate(
        "() => document.querySelectorAll('#slide-root > *').length"
    )


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


async def test_backward_seek_unapplies_structural_ops(browser_page, timeline_dict):
    """The decisive test for D5: rewinding must remove nodes that had entered.

    Ops only ever apply forward and are never individually undone, so the ONLY
    thing that can retract `n2` (which enters at t=1000) is the reset-and-replay
    in seek(). Without it `_applied` stays saturated, the node stays in the DOM,
    and t=500 renders a scene the renderer would never produce.
    """
    await serve(browser_page, timeline_dict)

    await browser_page.evaluate("() => window.AuditoriumEngine.seek(1200)")
    assert await child_count(browser_page) == 2
    assert await browser_page.evaluate("() => !!document.querySelector('#n2')")

    await browser_page.evaluate("() => window.AuditoriumEngine.seek(500)")
    assert await child_count(browser_page) == 1, (
        "rewinding left a node in the DOM that has not entered yet at t=500"
    )
    assert await browser_page.evaluate("() => !document.querySelector('#n2')")


async def test_rewound_state_matches_a_freshly_loaded_engine(browser_page, timeline_dict):
    """Ground truth is a fresh load, not a second forward sweep.

    The earlier form of this test compared two forward passes of the same
    engine, which is self-referential: a constant function satisfies it. Here
    each probe is compared against the state a newly-loaded engine reaches by
    seeking straight to that time — an independent reference the rewind path
    has to agree with.
    """
    probes = [0, 250, 500, 750, 1000, 1250]

    await serve(browser_page, timeline_dict)
    reference = []
    for t in probes:
        await browser_page.evaluate("(tl) => window.AuditoriumEngine.load(tl)", timeline_dict)
        await browser_page.evaluate("(t) => window.AuditoriumEngine.seek(t)", t)
        reference.append(
            (await opacity_of(browser_page), await x_of(browser_page), await child_count(browser_page))
        )

    await serve(browser_page, timeline_dict)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(3000)")
    rewound = []
    for t in reversed(probes):
        await browser_page.evaluate("(t) => window.AuditoriumEngine.seek(t)", t)
        rewound.append(
            (await opacity_of(browser_page), await x_of(browser_page), await child_count(browser_page))
        )
    rewound.reverse()

    assert rewound == reference


async def test_append_does_not_add_a_wrapper_element(browser_page):
    """The node's own element goes into the DOM, not a div around it.

    An extra wrapper breaks flex sizing: a `flex: 1` container cannot grow
    through an unstyled div, so nested row layouts collapse to their natural
    height. Pinning the tag name catches it directly.
    """
    tl = Timeline(meta={"title": "wrap"})
    tl.nodes.append(Node(id="n1", layer="dom", html="<p>hi</p>"))
    tl.ops.append(Op(t=0, action="append", node="n1"))
    await serve(browser_page, tl.to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")

    tag = await browser_page.evaluate("() => document.getElementById('n1').tagName")
    assert tag == "P", f"expected the node's own <p>, got a <{tag.lower()}> wrapper"
    depth = await browser_page.evaluate(
        "() => document.getElementById('n1').parentElement.id"
    )
    assert depth == "slide-root"


async def test_flex_sizing_propagates_to_appended_content(browser_page):
    """The behaviour the wrapper broke: a flex child must actually grow."""
    tl = Timeline(meta={"title": "flex"})
    tl.nodes.append(
        Node(
            id="n1",
            layer="dom",
            html='<div style="display:flex;flex-direction:column;height:400px">'
            '<div id="grower" style="flex:1">x</div></div>',
        )
    )
    tl.ops.append(Op(t=0, action="append", node="n1"))
    await serve(browser_page, tl.to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")

    h = await browser_page.evaluate(
        "() => Math.round(document.getElementById('grower').getBoundingClientRect().height)"
    )
    assert h > 300, f"flex child did not grow (height {h}); a wrapper is blocking it"
