from auditorium.nodes import Anchor, Circle, Line
from auditorium.scene import SceneContext
from auditorium.timeline import Timeline


def make_scene(**kw):
    tl = Timeline()
    return SceneContext(tl, **kw), tl


async def test_show_emits_a_node_and_an_append_op_at_the_current_time():
    s, tl = make_scene()
    handle = await s.show("<p>hi</p>")
    assert len(tl.nodes) == 1
    assert tl.nodes[0].id == handle.id
    assert tl.ops[0].action == "append"
    assert tl.ops[0].t == 0


async def test_wait_advances_the_clock_without_emitting_anything():
    s, tl = make_scene()
    await s.wait(1.5)
    assert s.t_ms == 1500
    assert tl.ops == []
    assert tl.tracks == []


async def test_play_appends_a_track_and_advances_the_clock():
    s, tl = make_scene()
    h = await s.show("<p>hi</p>")
    await s.play(h.animate.fade_in(), run_time=0.5)
    assert len(tl.tracks) == 1
    track = tl.tracks[0]
    assert track.prop == "opacity"
    assert (track.start, track.end) == (0, 500)
    assert s.t_ms == 500


async def test_multiple_animations_in_one_play_overlap():
    s, tl = make_scene()
    a = await s.show("<p>a</p>")
    b = await s.show("<p>b</p>")
    await s.play(a.animate.fade_in(), b.animate.fade_in(), run_time=0.5)
    assert [(t.start, t.end) for t in tl.tracks] == [(0, 500), (0, 500)]
    assert s.t_ms == 500


async def test_lag_staggers_starts_and_the_clock_covers_the_last_one():
    s, tl = make_scene()
    a = await s.show("<p>a</p>")
    b = await s.show("<p>b</p>")
    await s.play(a.animate.fade_in(), b.animate.fade_in(), run_time=0.5, lag=0.2)
    assert [(t.start, t.end) for t in tl.tracks] == [(0, 500), (200, 700)]
    assert s.t_ms == 700


async def test_beat_records_a_pause_and_advances_one_millisecond():
    """The 1ms keeps post-beat content from being visible at the beat itself."""
    s, tl = make_scene()
    await s.wait(1.0)
    await s.beat()
    assert tl.beats[0].t == 1000
    assert tl.beats[0].hold_ms == 0
    assert s.t_ms == 1001


async def test_content_after_a_beat_is_not_visible_at_the_beat():
    s, tl = make_scene()
    await s.show("<p>before</p>")
    await s.beat()
    await s.show("<p>after</p>")
    beat_t = tl.beats[0].t
    visible_at_beat = [o for o in tl.ops if o.t <= beat_t]
    assert len(visible_at_beat) == 1


async def test_beat_hold_defaults_come_from_the_scene():
    s, tl = make_scene(beat_hold_ms=1500)
    await s.beat()
    assert tl.beats[0].hold_ms == 1500


async def test_explicit_beat_hold_overrides_the_scene_default():
    s, tl = make_scene(beat_hold_ms=1500)
    await s.beat(hold=0.25)
    assert tl.beats[0].hold_ms == 250


async def test_ease_names_map_to_css_easing_functions():
    s, tl = make_scene()
    h = await s.show("<p>hi</p>")
    await s.play(h.animate.fade_in(), run_time=0.5, ease="out-cubic")
    assert tl.tracks[0].ease == "cubic-bezier(0.33, 1, 0.68, 1)"


async def test_move_by_emits_two_tracks_one_per_axis():
    s, tl = make_scene()
    h = await s.show("<p>hi</p>")
    await s.play(h.animate.move_by(400, 200), run_time=0.8)
    props = sorted(t.prop for t in tl.tracks)
    assert props == ["transform.x", "transform.y"]


async def test_nothing_sleeps_during_compilation():
    import time
    s, _ = make_scene()
    h = await s.show("<p>hi</p>")
    started = time.monotonic()
    await s.play(h.animate.fade_in(), run_time=5.0)
    await s.wait(10.0)
    assert time.monotonic() - started < 0.5
    assert s.t_ms == 15000


async def test_draw_appends_an_svg_node_at_the_current_clock():
    s, tl = make_scene()
    await s.wait(2.0)
    handle = await s.draw(Circle(at=(100, 100), r=20))
    node = next(n for n in tl.nodes if n.id == handle.id)
    assert node.layer == "svg"
    assert node.svg["kind"] == "circle"
    assert [o.t for o in tl.ops if o.node == handle.id] == [2000]


async def test_a_handle_yields_anchors_on_every_side():
    s, tl = make_scene()
    box = await s.show("<div>x</div>")
    for side in ("left", "right", "top", "bottom", "center"):
        anchor = getattr(box, side)
        assert isinstance(anchor, Anchor)
        assert (anchor.node, anchor.side) == (box.id, side)


async def test_an_anchor_survives_into_the_timeline_unresolved():
    """Python must never turn a symbolic anchor into a number (D6)."""
    s, tl = make_scene()
    box = await s.show("<div>x</div>")
    line = await s.draw(Line(from_=box.right, to=(400, 300)))
    node = next(n for n in tl.nodes if n.id == line.id)
    assert node.svg["from"] == {"anchor": {"node": box.id, "side": "right"}}


async def test_draw_on_animates_dashoffset_to_zero():
    s, tl = make_scene()
    line = await s.draw(Line(from_=(0, 0), to=(100, 0)))
    await s.play(line.animate.draw_on(), run_time=0.5)
    track = next(t for t in tl.tracks if t.node == line.id)
    assert (track.prop, track.from_, track.to) == ("stroke.dashoffset", 1.0, 0.0)
    assert (track.start, track.end) == (0, 500)


async def test_an_svg_node_ignores_region_scoping():
    """SVG coordinates are viewport coordinates; parenting into a column lies."""
    s, tl = make_scene()
    cols = await s.columns(2)
    async with cols[0]:
        line = await s.draw(Line(from_=(0, 0), to=(10, 10)))
    node = next(n for n in tl.nodes if n.id == line.id)
    assert node.parent == "svg-layer"


async def test_rotate_by_emits_a_rotation_track():
    """Rotation was simply absent: the engine knew x, y and scale only."""
    tl = Timeline()
    s = SceneContext(tl)
    h = await s.show("<div>x</div>")
    await s.play(h.animate.rotate_by(720), run_time=2.0)
    track = next(t for t in tl.tracks if t.prop == "transform.rotate")
    assert (track.from_, track.to) == (0.0, 720)
    assert (track.start, track.end) == (0, 2000)


async def test_show_into_parents_a_node_under_another():
    """Epicycle arms nest: each arm's rotation composes onto its parent's."""
    tl = Timeline()
    s = SceneContext(tl)
    outer = await s.show("<div>outer</div>")
    inner = await s.show("<div>inner</div>", into=outer)
    node = next(n for n in tl.nodes if n.id == inner.id)
    assert node.parent == outer.id


async def test_show_into_beats_the_region_stack():
    """An explicit parent is explicit; region scoping must not override it."""
    tl = Timeline()
    s = SceneContext(tl)
    host = await s.show("<div>host</div>")
    cols = await s.columns(2)
    async with cols[0]:
        child = await s.show("<div>child</div>", into=host)
    node = next(n for n in tl.nodes if n.id == child.id)
    assert node.parent == host.id


async def test_show_into_does_not_wrap_the_content():
    """Composition needs the author's element, not a wrapper around it.

    A wrapper is invisible in flow layout and fatal here: the handle would
    refer to the wrapper, so the next `into=` would parent into that instead
    of the positioned element, and absolute coordinates would resolve against
    the wrong box.
    """
    tl = Timeline()
    s = SceneContext(tl)
    host = await s.show("<div>host</div>")
    child = await s.show("<b id='inner'>x</b>", into=host)
    node = next(n for n in tl.nodes if n.id == child.id)
    assert node.html == "<b id='inner'>x</b>"
