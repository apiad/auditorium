"""The geometric scene graph: what CSS cannot express.

SVG nodes live in a full-viewport overlay sharing one coordinate space with
the DOM layer, so an anchor resolves to a viewport point that is directly
usable as an SVG coordinate.

Nothing here computes geometry. An ``Anchor`` is a *symbolic* reference --
"the right edge of n1" -- resolved in the browser at seek time (D6). That is
what lets an arrow track its box through motion and through flex reflow
without Python modelling CSS layout, and it is why these classes serialize
endpoints rather than points.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SIDES = ("left", "right", "top", "bottom", "center")


@dataclass
class Anchor:
    """A symbolic reference to a point on a DOM node.

    Validated at construction: an unchecked typo becomes an arrow that
    silently does not render, three layers away from the mistake.
    """
    node: str
    side: str = "center"

    def __post_init__(self) -> None:
        if self.side not in SIDES:
            raise ValueError(
                f"unknown anchor side {self.side!r}. Use one of: {', '.join(SIDES)}"
            )

    def to_dict(self) -> dict:
        return {"node": self.node, "side": self.side}


def _endpoint(value) -> dict:
    """Normalize an endpoint to a symbolic anchor or a literal point.

    A tuple is a fixed viewport coordinate; an Anchor is a promise the browser
    keeps at seek time. Python never turns the second into the first.
    """
    if isinstance(value, Anchor):
        return {"anchor": value.to_dict()}
    x, y = value
    return {"point": [x, y]}


class _Stroked:
    """Shared stroke styling.

    A plain mixin rather than a base dataclass on purpose: dataclass
    inheritance puts the *base's* fields first, so ``Path("M0,0 L10,10")``
    would bind its command string to ``stroke``. Each node therefore declares
    its own fields first and the styling after.
    """

    def _stroke_dict(self) -> dict:
        return {"stroke": self.stroke, "width": self.width, "dash": self.dash}


@dataclass
class Line(_Stroked):
    from_: object
    to: object
    stroke: str = "currentColor"
    width: float = 2
    dash: str | None = None

    def to_svg_dict(self) -> dict:
        return {"kind": "line", "from": _endpoint(self.from_),
                "to": _endpoint(self.to), **self._stroke_dict()}


@dataclass
class Arrow(_Stroked):
    """A line that ends in a head. The head is an SVG marker, not a second node."""
    from_: object
    to: object
    stroke: str = "currentColor"
    width: float = 2
    dash: str | None = None

    def to_svg_dict(self) -> dict:
        return {"kind": "arrow", "from": _endpoint(self.from_),
                "to": _endpoint(self.to), **self._stroke_dict()}


@dataclass
class Circle(_Stroked):
    at: object
    r: float = 10
    fill: str = "none"
    stroke: str = "currentColor"
    width: float = 2
    dash: str | None = None

    def to_svg_dict(self) -> dict:
        x, y = self.at
        return {"kind": "circle", "at": [x, y], "r": self.r,
                "fill": self.fill, **self._stroke_dict()}


@dataclass
class Path(_Stroked):
    d: str
    fill: str = "none"
    stroke: str = "currentColor"
    width: float = 2
    dash: str | None = None

    def to_svg_dict(self) -> dict:
        return {"kind": "path", "d": self.d, "fill": self.fill,
                **self._stroke_dict()}
