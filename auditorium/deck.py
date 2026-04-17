from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class SlideInfo:
    """Metadata for a registered slide."""
    func: Callable
    title: str | None
    order: float | None

    @property
    def name(self) -> str:
        return self.title or self.func.__name__


class Deck:
    """Top-level object holding slides and presentation metadata."""

    def __init__(self, title: str = "Untitled", extra_css: str | None = None) -> None:
        self.title = title
        self.extra_css = extra_css
        self._slides: list[SlideInfo] = []

    def slide(
        self,
        func: Callable | None = None,
        *,
        order: float | None = None,
        title: str | None = None,
    ) -> Callable:
        """Decorator to register an async function as a slide."""
        def decorator(fn: Callable) -> Callable:
            self._slides.append(SlideInfo(func=fn, title=title, order=order))
            return fn

        if func is not None:
            return decorator(func)
        return decorator

    @property
    def slides(self) -> list[SlideInfo]:
        """Return slides in presentation order.

        Slides with explicit order come first (sorted by order),
        then slides without explicit order in registration order.
        """
        ordered = [(i, s) for i, s in enumerate(self._slides) if s.order is not None]
        unordered = [(i, s) for i, s in enumerate(self._slides) if s.order is None]
        ordered.sort(key=lambda x: x[1].order)
        unordered.sort(key=lambda x: x[0])
        return [s for _, s in ordered] + [s for _, s in unordered]
