import json

from auditorium.timeline import Beat, Marker, Node, Op, Timeline, Track


def test_empty_timeline_has_zero_duration():
    assert Timeline().duration_ms == 0


def test_duration_is_the_latest_of_ops_tracks_and_beats():
    tl = Timeline()
    tl.ops.append(Op(t=100, action="append", node="n1"))
    tl.tracks.append(Track(node="n1", prop="opacity", from_=0, to=1, start=0, end=500))
    tl.beats.append(Beat(t=900, hold_ms=0))
    assert tl.duration_ms == 900


def test_round_trips_through_dict():
    tl = Timeline(meta={"title": "T", "fps": 30, "size": [1920, 1080]})
    tl.nodes.append(Node(id="n1", layer="dom", html="<p>hi</p>", parent="root"))
    tl.ops.append(Op(t=0, action="append", node="n1"))
    tl.tracks.append(
        Track(node="n1", prop="opacity", from_=0, to=1, start=0, end=500, ease="ease-out")
    )
    tl.beats.append(Beat(t=500, hold_ms=1500))

    restored = Timeline.from_dict(tl.to_dict())

    assert restored.meta["title"] == "T"
    assert restored.nodes[0].html == "<p>hi</p>"
    assert restored.tracks[0].from_ == 0
    assert restored.beats[0].hold_ms == 1500
    assert restored.to_dict() == tl.to_dict()


def test_track_serializes_from_as_json_key_from():
    tl = Timeline()
    tl.tracks.append(Track(node="n1", prop="opacity", from_=0.0, to=1.0, start=0, end=1))
    d = tl.to_dict()
    assert "from" in d["tracks"][0]
    assert "from_" not in d["tracks"][0]


def test_is_json_serializable():
    import json
    tl = Timeline(meta={"title": "T"})
    tl.ops.append(Op(t=0, action="append", node="n1"))
    assert json.loads(json.dumps(tl.to_dict()))["ops"][0]["t"] == 0


def test_markers_round_trip_through_json():
    tl = Timeline(meta={"title": "T"})
    tl.markers.append(Marker(t=0, title="Intro", notes_html="<p>hi</p>"))
    tl.markers.append(Marker(t=2500, title="Body"))
    back = Timeline.from_dict(json.loads(json.dumps(tl.to_dict())))
    assert [(m.t, m.title, m.notes_html) for m in back.markers] == [
        (0, "Intro", "<p>hi</p>"),
        (2500, "Body", ""),
    ]


def test_markers_do_not_extend_the_duration():
    """A marker labels time; it does not occupy any."""
    tl = Timeline()
    tl.ops.append(Op(t=100, action="clear"))
    tl.markers.append(Marker(t=9999, title="stray"))
    assert tl.duration_ms == 100
