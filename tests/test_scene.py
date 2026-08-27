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


async def test_move_to_emits_two_tracks_one_per_axis():
    s, tl = make_scene()
    h = await s.show("<p>hi</p>")
    await s.play(h.animate.move_to(400, 200), run_time=0.8)
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
