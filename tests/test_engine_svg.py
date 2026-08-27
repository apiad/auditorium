"""The SVG overlay: geometry, anchors, and draw-on.

Two of these tests carry the design's weight rather than its surface.
`test_the_anchor_follows_the_node_when_the_node_animates` is what justifies
symbolic anchors at all -- an anchor resolved once at append time passes every
other test here and fails that one. And the read/write phase separation is
asserted structurally rather than by timing, because a benchmark on a loaded
machine measures the machine.
"""
import json
from pathlib import Path

from auditorium.nodes import Anchor, Arrow, Circle, Line
from auditorium.timeline import Node, Op, Timeline, Track

FIXTURE = Path(__file__).parent / "fixtures" / "svg_harness.html"
ENGINE = Path(__file__).parent.parent / "auditorium" / "static" / "engine.js"


async def serve(page, timeline_dict):
    """Load the harness with engine.js inlined, without a server."""
    engine_src = ENGINE.read_text()
    html = FIXTURE.read_text().replace(
        "/*ENGINE*/",
        f"{engine_src}\nwindow.AuditoriumEngine = AuditoriumEngine;",
    )
    await page.set_content(html)
    await page.evaluate(
        "(tl) => window.AuditoriumEngine.load(tl)", json.loads(json.dumps(timeline_dict))
    )


def _box_and_line(anchor_side="right", with_move=False, draw_on=False):
    """A 100x50 box at (50,100), plus a line anchored to it."""
    tl = Timeline(meta={"title": "svg"})
    tl.nodes.append(Node(
        id="n1", layer="dom",
        html="<div id='box' style='width:100px;height:50px;background:#ccc'></div>",
    ))
    tl.ops.append(Op(t=0, action="append", node="n1"))
    tl.nodes.append(Node(
        id="s1", layer="svg", parent="svg-layer",
        svg=Line(from_=Anchor("n1", anchor_side), to=(600, 400)).to_svg_dict(),
    ))
    tl.ops.append(Op(t=0, action="append", node="s1"))
    if with_move:
        tl.tracks.append(
            Track(node="n1", prop="transform.x", from_=0, to=200, start=0, end=1000)
        )
    if draw_on:
        tl.tracks.append(
            Track(node="s1", prop="stroke.dashoffset",
                  from_=1.0, to=0.0, start=0, end=1000)
        )
    return tl


async def _attr(page, selector, name):
    return await page.evaluate(
        "([sel, n]) => { const el = document.querySelector(sel);"
        " return el ? el.getAttribute(n) : null; }",
        [selector, name],
    )


async def test_an_svg_node_appears_in_the_overlay_not_the_slide_root(browser_page):
    await serve(browser_page, _box_and_line().to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    assert await browser_page.evaluate(
        "() => !!document.querySelector('#svg-layer > line#s1')"
    )
    assert await browser_page.evaluate(
        "() => !document.querySelector('#slide-root #s1')"
    )


async def test_the_element_is_a_real_svg_element(browser_page):
    """innerHTML on an HTML parent makes HTMLUnknownElements that never render."""
    await serve(browser_page, _box_and_line().to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    assert await browser_page.evaluate(
        "() => document.querySelector('#s1') instanceof SVGElement"
    ) is True


async def test_an_anchored_line_starts_at_the_right_edge_of_its_source(browser_page):
    await serve(browser_page, _box_and_line("right").to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    rect = await browser_page.evaluate(
        "() => { const r = document.getElementById('n1').getBoundingClientRect();"
        " return [r.right, r.top + r.height / 2]; }"
    )
    x1 = float(await _attr(browser_page, "#s1", "x1"))
    y1 = float(await _attr(browser_page, "#s1", "y1"))
    assert abs(x1 - rect[0]) < 1
    assert abs(y1 - rect[1]) < 1


async def test_each_side_resolves_to_a_different_point(browser_page):
    seen = {}
    for side in ("left", "right", "top", "bottom", "center"):
        await serve(browser_page, _box_and_line(side).to_dict())
        await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
        seen[side] = (
            float(await _attr(browser_page, "#s1", "x1")),
            float(await _attr(browser_page, "#s1", "y1")),
        )
    assert seen["left"][0] < seen["right"][0]
    assert seen["top"][1] < seen["bottom"][1]
    assert len(set(seen.values())) == 5


async def test_the_anchor_follows_the_node_when_the_node_animates(browser_page):
    """The claim that justifies symbolic anchors.

    An anchor resolved once at append time passes every other test in this
    file and fails this one.
    """
    await serve(browser_page, _box_and_line("right", with_move=True).to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    x_start = float(await _attr(browser_page, "#s1", "x1"))

    await browser_page.evaluate("() => window.AuditoriumEngine.seek(1000)")
    x_end = float(await _attr(browser_page, "#s1", "x1"))

    # The box translated 200px; its anchor must have travelled with it.
    assert abs((x_end - x_start) - 200) < 1


async def test_an_arrow_gets_a_head_marker(browser_page):
    tl = Timeline()
    tl.nodes.append(Node(id="s1", layer="svg", parent="svg-layer",
                         svg=Arrow(from_=(10, 10), to=(200, 200)).to_svg_dict()))
    tl.ops.append(Op(t=0, action="append", node="s1"))
    await serve(browser_page, tl.to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    assert "aud-arrowhead" in (await _attr(browser_page, "#s1", "marker-end") or "")
    assert await browser_page.evaluate(
        "() => !!document.querySelector('#svg-layer defs #aud-arrowhead')"
    )


async def test_a_literal_circle_lands_where_it_was_told(browser_page):
    tl = Timeline()
    tl.nodes.append(Node(id="s1", layer="svg", parent="svg-layer",
                         svg=Circle(at=(120, 340), r=25).to_svg_dict()))
    tl.ops.append(Op(t=0, action="append", node="s1"))
    await serve(browser_page, tl.to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    assert float(await _attr(browser_page, "#s1", "cx")) == 120
    assert float(await _attr(browser_page, "#s1", "cy")) == 340
    assert float(await _attr(browser_page, "#s1", "r")) == 25


async def _dashoffset(page):
    return await page.evaluate(
        "() => parseFloat(getComputedStyle(document.getElementById('s1')).strokeDashoffset)"
    )


async def test_draw_on_leaves_the_stroke_hidden_at_its_start(browser_page):
    await serve(browser_page, _box_and_line(draw_on=True).to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    assert await _dashoffset(browser_page) == 1
    assert await _attr(browser_page, "#s1", "pathLength") == "1"


async def test_draw_on_leaves_the_stroke_drawn_after_it_finishes(browser_page):
    await serve(browser_page, _box_and_line(draw_on=True).to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(1000)")
    assert await _dashoffset(browser_page) == 0


async def test_draw_on_is_halfway_at_the_midpoint(browser_page):
    await serve(browser_page, _box_and_line(draw_on=True).to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(500)")
    value = await _dashoffset(browser_page)
    assert 0.3 < value < 0.7


async def test_reset_clears_the_overlay_but_keeps_the_defs(browser_page):
    """Dropping <defs> on rewind makes every later arrow render headless."""
    await serve(browser_page, _box_and_line().to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(1000)")
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    assert await browser_page.evaluate(
        "() => document.querySelectorAll('#svg-layer > line').length"
    ) == 1
    assert await browser_page.evaluate(
        "() => !!document.querySelector('#svg-layer defs #aud-arrowhead')"
    )


async def test_anchor_resolution_reads_every_rect_before_writing_any(browser_page):
    """The D6 guard, asserted structurally rather than by timing.

    Interleaved reads and writes thrash layout: 182ms per frame at 2000
    anchors against a 33ms budget. A benchmark would prove this machine is
    fast today; the ordering property is what actually has to hold.
    """
    tl = Timeline(meta={"title": "svg"})
    tl.nodes.append(Node(id="n1", layer="dom",
                         html="<div style='width:80px;height:40px'></div>"))
    tl.ops.append(Op(t=0, action="append", node="n1"))
    for i in range(3):
        tl.nodes.append(Node(
            id=f"s{i}", layer="svg", parent="svg-layer",
            svg=Line(from_=Anchor("n1", "right"), to=(500, 100 * i)).to_svg_dict(),
        ))
        tl.ops.append(Op(t=0, action="append", node=f"s{i}"))
    await serve(browser_page, tl.to_dict())

    # Ops applied first, uninstrumented: the property under test is the
    # ordering within ONE anchor pass, and folding two seeks into one trace
    # would show the second seek's reads after the first seek's writes.
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")

    trace = await browser_page.evaluate(
        """() => {
            const log = [];
            const realRect = Element.prototype.getBoundingClientRect;
            const realSet = Element.prototype.setAttribute;
            Element.prototype.getBoundingClientRect = function (...a) {
                log.push('read');
                return realRect.apply(this, a);
            };
            Element.prototype.setAttribute = function (name, value) {
                if (['x1', 'y1', 'x2', 'y2', 'cx', 'cy'].includes(name)) log.push('write');
                return realSet.call(this, name, value);
            };
            try {
                window.AuditoriumEngine.seek(10);
            } finally {
                Element.prototype.getBoundingClientRect = realRect;
                Element.prototype.setAttribute = realSet;
            }
            return log;
        }"""
    )
    assert trace.count("read") >= 3, f"expected one read per anchored line: {trace}"
    assert trace.count("write") >= 6, f"expected x1/y1 per anchored line: {trace}"
    # No read may follow a write inside one pass.
    tail = trace[trace.index("write"):]
    assert "read" not in tail, f"reads interleaved with writes: {trace}"


async def _serve_scaled(page, timeline_dict, scale=0.5):
    """The same harness, but with the stage transform-scaled.

    This is the shape the preview and presenter clients actually use: a fixed
    1920x1080 stage scaled to fit. getBoundingClientRect reports screen pixels
    there, which are NOT the overlay's user units -- so an anchor written
    without converting through the overlay's screen CTM lands at the wrong
    place by exactly the scale factor.
    """
    engine_src = ENGINE.read_text()
    html = FIXTURE.read_text().replace(
        "/*ENGINE*/", f"{engine_src}\nwindow.AuditoriumEngine = AuditoriumEngine;"
    )
    html = html.replace(
        "</style>",
        "#stage { position: relative; width: 800px; height: 600px;"
        f" transform-origin: top left; transform: scale({scale}); }}"
        " #svg-layer { position: absolute; inset: 0; width: 800px; height: 600px; }"
        "</style>",
    )
    html = html.replace('<div id="slide-root"></div>', '<div id="stage"><div id="slide-root"></div>')
    html = html.replace("</svg>", "</svg></div>")
    await page.set_content(html)
    await page.evaluate(
        "(tl) => window.AuditoriumEngine.load(tl)", json.loads(json.dumps(timeline_dict))
    )


async def test_anchors_land_correctly_inside_a_scaled_stage(browser_page):
    await _serve_scaled(browser_page, _box_and_line("right").to_dict(), scale=0.5)
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")

    # The box's own position inside the (unscaled) stage coordinate system is
    # what the overlay must agree with: left 50px + width 100px = 300... in
    # user units, independent of the scale applied to the whole stage.
    x1 = float(await _attr(browser_page, "#s1", "x1"))
    expected = await browser_page.evaluate(
        "() => { const el = document.getElementById('n1');"
        " return el.offsetLeft + el.offsetWidth; }"
    )
    assert abs(x1 - expected) < 1, f"anchor at {x1}, box right edge at {expected}"


async def test_a_dash_pattern_is_normalized_to_the_shape_length(browser_page):
    """Dash units are fractions of the shape, because pathLength is 1.

    Pinned by a test rather than left as a surprise: a pattern written in
    pixels would render as a solid line, which reads as "dashes are broken".
    """
    tl = Timeline()
    tl.nodes.append(Node(
        id="s1", layer="svg", parent="svg-layer",
        svg=Line(from_=(0, 0), to=(400, 0), dash="0.05 0.02").to_svg_dict(),
    ))
    tl.ops.append(Op(t=0, action="append", node="s1"))
    await serve(browser_page, tl.to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    assert await _attr(browser_page, "#s1", "stroke-dasharray") == "0.05 0.02"
    assert await _attr(browser_page, "#s1", "pathLength") == "1"


async def test_clear_empties_the_overlay_too(browser_page):
    """A scene boundary must wipe geometry, not just the DOM layer.

    Found by looking at the demo rather than by a test: the arrow, rule and
    circle from the Geometry scene were still drawn over the "Thank You"
    slide, because `clear` only ever emptied #slide-root. The overlay
    accumulated for the rest of the deck.
    """
    tl = _box_and_line()
    tl.ops.append(Op(t=500, action="clear"))
    await serve(browser_page, tl.to_dict())
    await browser_page.evaluate("() => window.AuditoriumEngine.seek(0)")
    assert await browser_page.evaluate(
        "() => document.querySelectorAll('#svg-layer > line').length"
    ) == 1

    await browser_page.evaluate("() => window.AuditoriumEngine.seek(600)")
    assert await browser_page.evaluate(
        "() => document.querySelectorAll('#svg-layer > line').length"
    ) == 0
    # The arrowhead marker still has to survive, as it does on reset.
    assert await browser_page.evaluate(
        "() => !!document.querySelector('#svg-layer defs #aud-arrowhead')"
    )
