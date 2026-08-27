"""The geometric vocabulary: pure data, no browser.

An anchor is a promise the browser keeps at seek time, never a number Python
computed. That is the whole point of D6 -- resolving in the browser keeps CSS
layout modelling out of Python, so an arrow tracks its box through motion and
flex reflow without anyone modelling flex.
"""
import json

import pytest

from auditorium.nodes import Anchor, Arrow, Circle, Line, Path
from auditorium.timeline import Node, Timeline


def test_a_line_between_two_anchors_serializes_symbolically():
    line = Line(from_=Anchor("n1", "right"), to=Anchor("n2", "left"))
    d = line.to_svg_dict()
    assert d["kind"] == "line"
    assert d["from"] == {"anchor": {"node": "n1", "side": "right"}}
    assert d["to"] == {"anchor": {"node": "n2", "side": "left"}}


def test_a_line_between_two_points_serializes_literally():
    d = Line(from_=(10, 20), to=(30, 40)).to_svg_dict()
    assert d["from"] == {"point": [10, 20]}
    assert d["to"] == {"point": [30, 40]}


def test_an_endpoint_may_mix_an_anchor_and_a_point():
    d = Arrow(from_=Anchor("n1", "bottom"), to=(400, 300)).to_svg_dict()
    assert d["from"] == {"anchor": {"node": "n1", "side": "bottom"}}
    assert d["to"] == {"point": [400, 300]}


def test_an_unknown_anchor_side_is_rejected_at_construction():
    """Otherwise a typo is an arrow that silently does not render."""
    with pytest.raises(ValueError, match="side"):
        Anchor("n1", "northeast")


def test_every_documented_side_is_accepted():
    for side in ("left", "right", "top", "bottom", "center"):
        assert Anchor("n1", side).side == side


def test_an_arrow_declares_itself_as_one():
    assert Arrow(from_=(0, 0), to=(1, 1)).to_svg_dict()["kind"] == "arrow"


def test_a_circle_carries_its_centre_and_radius():
    d = Circle(at=(100, 200), r=30).to_svg_dict()
    assert d["kind"] == "circle"
    assert d["at"] == [100, 200]
    assert d["r"] == 30


def test_a_path_carries_its_command_string():
    d = Path("M0,0 L100,100").to_svg_dict()
    assert d["kind"] == "path"
    assert d["d"] == "M0,0 L100,100"


def test_stroke_styling_round_trips():
    d = Line(from_=(0, 0), to=(1, 1), stroke="#f00", width=5, dash="4 2").to_svg_dict()
    assert (d["stroke"], d["width"], d["dash"]) == ("#f00", 5, "4 2")


def test_svg_nodes_round_trip_through_json():
    tl = Timeline()
    tl.nodes.append(Node(
        id="s1", layer="svg",
        svg=Arrow(from_=Anchor("n1", "right"), to=(400, 300)).to_svg_dict(),
    ))
    back = Timeline.from_dict(json.loads(json.dumps(tl.to_dict())))
    assert back.nodes[0].layer == "svg"
    assert back.nodes[0].svg["kind"] == "arrow"
    assert back.nodes[0].svg["from"]["anchor"]["side"] == "right"


def test_a_dom_node_carries_no_svg_payload():
    tl = Timeline()
    tl.nodes.append(Node(id="n1", layer="dom", html="<p>x</p>"))
    back = Timeline.from_dict(json.loads(json.dumps(tl.to_dict())))
    assert back.nodes[0].svg is None
