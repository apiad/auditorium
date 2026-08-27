"""Compile-time scene construction.

Nothing here executes in real time. ``play()`` records tracks and advances a
virtual clock; the authoring script runs to completion before anything is
displayed. That is what makes arbitrary Python — loops, recursion, numpy —
usable for animation, and what makes the result seekable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auditorium.timeline import Beat, Node, Op, Timeline, Track

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


@dataclass
class NodeHandle:
    """Author-facing reference to a scene node."""
    id: str

    @property
    def animate(self) -> AnimateProxy:
        return AnimateProxy(self.id)


class SceneContext:
    def __init__(self, timeline: Timeline, *, beat_hold_ms: int = 0) -> None:
        self._tl = timeline
        self._t = 0
        self._counter = 0
        self._beat_hold_ms = beat_hold_ms

    @property
    def t_ms(self) -> int:
        return self._t

    def _next_id(self) -> str:
        self._counter += 1
        return f"n{self._counter}"

    async def show(self, content: Any, *, element_id: str | None = None) -> NodeHandle:
        from auditorium.slide import _jupyter_to_html

        node_id = element_id or self._next_id()
        self._tl.nodes.append(
            Node(id=node_id, layer="dom", html=f"<div>{_jupyter_to_html(content)}</div>")
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
