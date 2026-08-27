"""Compile-time scene construction.

Nothing here executes in real time. ``play()`` records tracks and advances a
virtual clock; the authoring script runs to completion before anything is
displayed. That is what makes arbitrary Python — loops, recursion, numpy —
usable for animation, and what makes the result seekable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auditorium.nodes import Anchor
from auditorium.slide import ConstructionVocabulary
from auditorium.timeline import Beat, Node, Op, Timeline, Track

# The overlay element every geometric node parents into. Shared with
# engine.js, which looks it up by this id.
SVG_LAYER_ID = "svg-layer"

EASINGS = {
    "linear": "linear",
    "ease": "ease",
    "in": "ease-in",
    "out": "ease-out",
    "in-out": "ease-in-out",
    "out-cubic": "cubic-bezier(0.33, 1, 0.68, 1)",
    "in-cubic": "cubic-bezier(0.32, 0, 0.67, 0)",
    "out-back": "cubic-bezier(0.34, 1.56, 0.64, 1)",
}


def resolve_ease(name: str) -> str:
    """Map a friendly easing name to a CSS easing function.

    Unknown values pass through so callers can supply raw cubic-bezier().
    """
    return EASINGS.get(name, name)


@dataclass
class AnimSpec:
    """A description of one property animation. Produced by the .animate proxy."""
    node: str
    prop: str
    from_: float | None
    to: float


class AnimateProxy:
    """Turns ``handle.animate.move_to(x, y)`` into AnimSpec objects.

    Returns descriptions; mutates nothing. ``play()`` decides when they run.
    """

    def __init__(self, node_id: str) -> None:
        self._node = node_id

    def fade_in(self) -> list[AnimSpec]:
        return [AnimSpec(self._node, "opacity", 0.0, 1.0)]

    def fade_out(self) -> list[AnimSpec]:
        return [AnimSpec(self._node, "opacity", 1.0, 0.0)]

    def move_to(self, x: float, y: float) -> list[AnimSpec]:
        return [
            AnimSpec(self._node, "transform.x", None, x),
            AnimSpec(self._node, "transform.y", None, y),
        ]

    def scale_to(self, factor: float) -> list[AnimSpec]:
        return [AnimSpec(self._node, "transform.scale", None, factor)]

    def draw_on(self) -> list[AnimSpec]:
        """Stroke a geometric node into existence along its own length.

        Normalized units: every stroked SVG node is created with
        ``pathLength="1"`` and ``stroke-dasharray="1"``, so the offset runs
        1 -> 0 regardless of the shape's actual length. That matters because
        an anchored line has no fixed length -- it changes whenever the DOM
        node it points at moves, and a measured dash pattern would go stale
        on the next frame.
        """
        return [AnimSpec(self._node, "stroke.dashoffset", 1.0, 0.0)]


@dataclass
class NodeHandle:
    """Author-facing reference to a scene node."""
    id: str

    @property
    def animate(self) -> AnimateProxy:
        return AnimateProxy(self.id)

    # Anchors. Each returns a symbolic reference the browser resolves at seek
    # time, so `Arrow(from_=box_a.right, to=box_b.left)` tracks both boxes
    # through motion and through flex reflow without Python knowing where
    # either of them is.
    @property
    def left(self) -> Anchor:
        return Anchor(self.id, "left")

    @property
    def right(self) -> Anchor:
        return Anchor(self.id, "right")

    @property
    def top(self) -> Anchor:
        return Anchor(self.id, "top")

    @property
    def bottom(self) -> Anchor:
        return Anchor(self.id, "bottom")

    @property
    def center(self) -> Anchor:
        return Anchor(self.id, "center")


class SceneContext(ConstructionVocabulary):
    """The 4.0 authoring surface: the full vocabulary plus a timeline clock.

    Inherits every construction method rather than reimplementing them. Those
    methods are timing-agnostic — they describe *what* appears, never *when* —
    so a scene and a slide build content identically and differ only in how
    they mark time.
    """

    def __init__(self, timeline: Timeline, *, beat_hold_ms: int = 0) -> None:
        self._tl = timeline
        self._t = 0
        self._counter = 0
        self._beat_hold_ms = beat_hold_ms
        self._target_stack: list[str] = []

    @property
    def _scene(self) -> SceneContext:
        """The vocabulary emits through ``self._scene``; for a scene that is itself."""
        return self

    @property
    def t_ms(self) -> int:
        return self._t

    def _next_id(self) -> str:
        self._counter += 1
        return f"n{self._counter}"

    async def show(self, content: Any, *, element_id: str | None = None) -> NodeHandle:
        """Append content and return a handle you can animate.

        Routes through the inherited vocabulary so region scoping
        (``async with column:``) applies here exactly as it does on a slide;
        the only difference is that a scene gets a handle back.
        """
        node_id = await super().show(content, element_id=element_id)
        return NodeHandle(id=node_id)

    async def draw(self, shape: Any) -> NodeHandle:
        """Append a geometric node to the SVG overlay and return its handle.

        Deliberately not routed through the region stack the way ``show`` is:
        an SVG node's coordinates are viewport coordinates, so parenting it
        into a column would claim a containment that does not exist.
        """
        node_id = self._next_id()
        self._tl.nodes.append(
            Node(id=node_id, layer="svg", parent=SVG_LAYER_ID,
                 svg=shape.to_svg_dict())
        )
        self._tl.ops.append(Op(t=self._t, action="append", node=node_id))
        return NodeHandle(id=node_id)

    async def play(
        self,
        *anims: list[AnimSpec],
        run_time: float = 1.0,
        ease: str = "linear",
        lag: float = 0.0,
    ) -> None:
        """Record one or more animations starting now. Advances the clock."""
        css_ease = resolve_ease(ease)
        duration = int(run_time * 1000)
        end = self._t
        for i, spec_list in enumerate(anims):
            start = self._t + int(lag * 1000 * i)
            for spec in spec_list:
                self._tl.tracks.append(
                    Track(
                        node=spec.node,
                        prop=spec.prop,
                        from_=spec.from_ if spec.from_ is not None else 0.0,
                        to=spec.to,
                        start=start,
                        end=start + duration,
                        ease=css_ease,
                    )
                )
            end = max(end, start + duration)
        self._t = end

    async def beat(self, hold: float | None = None) -> None:
        """Record a pause point and advance the clock by exactly 1ms.

        The 1ms is not cosmetic. Ops apply when ``op.t <= t``, so without it
        content emitted after a beat would land on the same millisecond as
        the beat and be visible *at* the pause — the reveal would happen
        before the keypress that is supposed to trigger it.
        """
        hold_ms = self._beat_hold_ms if hold is None else int(hold * 1000)
        self._tl.beats.append(Beat(t=self._t, hold_ms=hold_ms))
        self._t += 1

    async def wait(self, seconds: float) -> None:
        """Advance the clock with nothing animating."""
        self._t += int(seconds * 1000)

    async def clear(self) -> None:
        """Remove everything currently on the slide root.

        Scene boundaries need this explicitly. Under the old protocol the
        server sent a `clear` message per slide; a timeline has no such
        implicit boundary, so without an op the whole deck accumulates into
        one continuous DOM.
        """
        await self._emit_op({"action": "clear"})

    async def _emit_op(self, mutation: dict) -> str | None:
        """Turn a vocabulary mutation dict into an Op. Returns the node id, if any.

        The construction vocabulary was written against a mutation protocol;
        rather than rewrite all of it, translate at this one boundary.
        """
        action = mutation["action"]
        if action == "append":
            node_id = mutation.get("element_id") or self._next_id()
            self._tl.nodes.append(
                Node(id=node_id, layer="dom", html=mutation["html"],
                     parent=mutation.get("target", "root").lstrip("#"))
            )
            self._tl.ops.append(Op(t=self._t, action="append", node=node_id))
            return node_id
        self._tl.ops.append(
            Op(t=self._t, action=action, selector=mutation.get("selector"),
               html=mutation.get("html"), cls=mutation.get("cls"))
        )
        return None
