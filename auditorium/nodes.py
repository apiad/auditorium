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

from dataclasses import dataclass

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


SERIES_MAX = 4


class _Stroked:
    """Shared stroke styling.

    A node names a *role*, never a colour: ``series=2`` means "the second thing
    in this figure" and the theme decides what that looks like. That is what
    keeps a figure legible when the theme changes, which is the whole premise
    of a composable theme system -- a deck authored on ``light`` and presented
    on ``dark`` keeps its meaning. ``stroke=`` still accepts a literal for
    anyone who wants one, and ``currentColor`` still works; it is simply no
    longer the default, because as the default it made every shape on every
    theme the same undifferentiated foreground colour.

    ``dash`` is expressed in NORMALIZED units -- fractions of the shape's own
    length -- because every stroked node is created with ``pathLength="1"`` so
    that draw-on works without measuring geometry anchors may be about to
    change. ``dash="0.05 0.02"`` is a 5% dash with a 2% gap, and is
    resolution-independent as a result. A pattern in pixels would silently
    render as a solid line.

    A plain mixin rather than a base dataclass on purpose: dataclass
    inheritance puts the *base's* fields first, so ``Path("M0,0 L10,10")``
    would bind its command string to ``stroke``. Each node therefore declares
    its own fields first and the styling after.
    """

    def __post_init__(self) -> None:
        """Validate at construction, not at serialization.

        Defined on the mixin so every node dataclass inherits it -- dataclasses
        call __post_init__ wherever it is found. A bad series caught here names
        the offending call; caught at render time it is a black line three
        layers away from the mistake.
        """
        if not 1 <= self.series <= SERIES_MAX:
            raise ValueError(
                f"series must be 1..{SERIES_MAX}, got {self.series}. A fifth "
                "simultaneous colour is past the point where colour explains "
                "anything, and would resolve to an undefined variable -- which "
                "renders black on every theme with no error."
            )

    def _stroke_dict(self) -> dict:
        if self.stroke is not None:
            stroke = self.stroke
        elif self.muted:
            stroke = "var(--aud-geom-muted)"
        else:
            stroke = f"var(--aud-geom-{self.series})"
        width = self.width if self.width is not None else "var(--aud-geom-width)"
        return {"stroke": stroke, "width": width, "dash": self.dash}


@dataclass
class Line(_Stroked):
    from_: object
    to: object
    series: int = 1
    muted: bool = False
    stroke: str | None = None
    width: float | None = None
    dash: str | None = None

    def to_svg_dict(self) -> dict:
        return {"kind": "line", "from": _endpoint(self.from_),
                "to": _endpoint(self.to), **self._stroke_dict()}


@dataclass
class Arrow(_Stroked):
    """A line that ends in a head. The head is an SVG marker, not a second node."""
    from_: object
    to: object
    series: int = 1
    muted: bool = False
    stroke: str | None = None
    width: float | None = None
    dash: str | None = None

    def to_svg_dict(self) -> dict:
        return {"kind": "arrow", "from": _endpoint(self.from_),
                "to": _endpoint(self.to), **self._stroke_dict()}


@dataclass
class Circle(_Stroked):
    at: object
    r: float = 10
    fill: str = "none"
    series: int = 1
    muted: bool = False
    stroke: str | None = None
    width: float | None = None
    dash: str | None = None

    def to_svg_dict(self) -> dict:
        x, y = self.at
        return {"kind": "circle", "at": [x, y], "r": self.r,
                "fill": self.fill, **self._stroke_dict()}


@dataclass
class Path(_Stroked):
    d: str
    fill: str = "none"
    series: int = 1
    muted: bool = False
    stroke: str | None = None
    width: float | None = None
    dash: str | None = None

    def to_svg_dict(self) -> dict:
        return {"kind": "path", "d": self.d, "fill": self.fill,
                **self._stroke_dict()}
