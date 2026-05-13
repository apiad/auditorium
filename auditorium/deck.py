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
    """Top-level object holding slides and presentation metadata.

    Theme knobs (all optional):
        margin: CSS shorthand for slide padding — "3rem" or "2rem 4rem".
            Maps to the --aud-slide-padding CSS variable.
        content_max_width: cap on text/list block width — "56rem".
            Maps to --aud-content-max-width.
        font_size: base slide font size — "1.5rem".
        line_height: base line height — "1.7".
        extra_css: arbitrary CSS appended after the theme. Takes precedence
            over both the default theme and the variables above.
    """

    def __init__(
        self,
        title: str = "Untitled",
        *,
        margin: str | None = None,
        content_max_width: str | None = None,
        font_size: str | None = None,
        line_height: str | None = None,
        extra_css: str | None = None,
    ) -> None:
        self.title = title
        self.margin = margin
        self.content_max_width = content_max_width
        self.font_size = font_size
        self.line_height = line_height
        self.extra_css = extra_css
        self._slides: list[SlideInfo] = []

    def theme_style_block(self) -> str:
        """Render this deck's theme overrides as an HTML <style> block."""
        vars_map = {
            "--aud-slide-padding": self.margin,
            "--aud-content-max-width": self.content_max_width,
            "--aud-font-size": self.font_size,
            "--aud-line-height": self.line_height,
        }
        decls = "\n".join(f"    {k}: {v};" for k, v in vars_map.items() if v)
        parts: list[str] = []
        if decls:
            parts.append(f":root {{\n{decls}\n}}")
        if self.extra_css:
            parts.append(self.extra_css)
        if not parts:
            return ""
        return "<style>\n" + "\n".join(parts) + "\n</style>"

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
