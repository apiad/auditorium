"""The compiled artifact: the contract between compiling and playing.

Pure data. No reference to Deck, SceneContext, or any live object — a
Timeline must survive a round trip through JSON unchanged, because that is
how it reaches the browser.

All times are integer milliseconds.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    """An element in the scene graph."""
    id: str
    layer: str = "dom"          # "dom" | "svg"
    html: str | None = None
    parent: str = "root"

    def to_dict(self) -> dict:
        return {"id": self.id, "layer": self.layer, "html": self.html, "parent": self.parent}

    @classmethod
    def from_dict(cls, d: dict) -> Node:
        return cls(id=d["id"], layer=d.get("layer", "dom"),
                   html=d.get("html"), parent=d.get("parent", "root"))


@dataclass
class Op:
    """A discrete structural mutation at an instant."""
    t: int
    action: str                 # "append" | "remove" | "replace" | "set_class" | "remove_class"
    node: str | None = None
    selector: str | None = None
    html: str | None = None
    cls: str | None = None

    def to_dict(self) -> dict:
        return {"t": self.t, "action": self.action, "node": self.node,
                "selector": self.selector, "html": self.html, "cls": self.cls}

    @classmethod
    def from_dict(cls, d: dict) -> Op:
        return cls(t=d["t"], action=d["action"], node=d.get("node"),
                   selector=d.get("selector"), html=d.get("html"), cls=d.get("cls"))


@dataclass
class Track:
    """A continuous property animation over an interval.

    ``start`` and ``end`` are absolute positions on the global timeline, not
    offsets from the node's own creation. The browser relies on that: every
    animation is declared with ``delay = start`` against a shared origin so
    one assignment of ``currentTime = t`` positions all of them correctly.
    """
    node: str
    prop: str
    from_: float
    to: float
    start: int
    end: int
    ease: str = "linear"

    def to_dict(self) -> dict:
        return {"node": self.node, "prop": self.prop, "from": self.from_,
                "to": self.to, "start": self.start, "end": self.end, "ease": self.ease}

    @classmethod
    def from_dict(cls, d: dict) -> Track:
        return cls(node=d["node"], prop=d["prop"], from_=d["from"], to=d["to"],
                   start=d["start"], end=d["end"], ease=d.get("ease", "linear"))


@dataclass
class Beat:
    """A pause point. Interactive mode waits here; rendering dwells ``hold_ms``."""
    t: int
    hold_ms: int = 0

    def to_dict(self) -> dict:
        return {"t": self.t, "hold_ms": self.hold_ms}

    @classmethod
    def from_dict(cls, d: dict) -> Beat:
        return cls(t=d["t"], hold_ms=d.get("hold_ms", 0))


@dataclass
class Timeline:
    meta: dict = field(default_factory=dict)
    nodes: list[Node] = field(default_factory=list)
    ops: list[Op] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    beats: list[Beat] = field(default_factory=list)
    audio: list[dict] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        candidates = [0]
        candidates += [o.t for o in self.ops]
        candidates += [t.end for t in self.tracks]
        candidates += [b.t + b.hold_ms for b in self.beats]
        return max(candidates)

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "meta": {**self.meta, "duration_ms": self.duration_ms},
            "nodes": [n.to_dict() for n in self.nodes],
            "ops": [o.to_dict() for o in self.ops],
            "tracks": [t.to_dict() for t in self.tracks],
            "beats": [b.to_dict() for b in self.beats],
            "audio": list(self.audio),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Timeline:
        meta = dict(d.get("meta", {}))
        meta.pop("duration_ms", None)
        return cls(
            meta=meta,
            nodes=[Node.from_dict(x) for x in d.get("nodes", [])],
            ops=[Op.from_dict(x) for x in d.get("ops", [])],
            tracks=[Track.from_dict(x) for x in d.get("tracks", [])],
            beats=[Beat.from_dict(x) for x in d.get("beats", [])],
            audio=list(d.get("audio", [])),
        )
