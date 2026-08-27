from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_THEMES_DIR = Path(__file__).parent / "themes"


def _resolve_theme_value(value: str) -> str:
    """Resolve a single theme value to CSS content.

    A value is treated as a filesystem path when it contains a path separator
    or ends in ``.css``; otherwise it's looked up as a builtin preset under
    ``auditorium/themes/<name>.css``. Raises ``ValueError`` on miss.
    """
    candidate = Path(value)
    if candidate.suffix == ".css" or "/" in value:
        if not candidate.exists():
            raise ValueError(f"theme file {value!r} not found")
        return candidate.read_text()
    builtin = _THEMES_DIR / f"{value}.css"
    if not builtin.exists():
        available = sorted(p.stem for p in _THEMES_DIR.glob("*.css"))
        listing = ", ".join(available) if available else "(none)"
        raise ValueError(f"unknown theme {value!r}. Available: {listing}")
    return builtin.read_text()


def resolve_themes(values: list[str]) -> str:
    """Resolve a list of theme values and concatenate the CSS in order.

    Later values cascade over earlier ones via normal CSS rules.
    """
    parts = [_resolve_theme_value(v) for v in values if v]
    return "\n\n".join(parts)


def _css_string_literal(s: str) -> str:
    """Quote a Python string for use as a CSS string value (in custom prop)."""
    return json.dumps(s)


_TRANSITION_ALIASES = {
    "fade": "aud-fade",
    "slide-left": "aud-slide-left",
    "slide-up": "aud-slide-up",
    "zoom": "aud-zoom",
    "none": "none",
}


def _resolve_transition(value: str) -> str:
    """Resolve a short transition name to a CSS animation-name value.

    Bare aliases like ``"fade"`` become ``"aud-fade"``. Anything that already
    looks like a CSS keyframe identifier (contains ``-`` or matches ``none``)
    passes through unchanged, so users can plug in custom keyframes.
    """
    return _TRANSITION_ALIASES.get(value, value)


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
        theme: name of a builtin theme preset (e.g. "academic"), a path to a
            ``.css`` file, or a list combining either. Themes cascade in order;
            later entries override earlier ones via standard CSS rules.
        transition: per-deck override for slide transitions. Accepts a short
            name (``"fade"``, ``"slide-left"``, ``"slide-up"``, ``"zoom"``,
            ``"none"``) or a raw CSS animation name. Overrides any
            ``--aud-transition`` set by the theme stack.
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
        theme: str | list[str] | None = None,
        transition: str | None = None,
        margin: str | None = None,
        content_max_width: str | None = None,
        font_size: str | None = None,
        line_height: str | None = None,
        extra_css: str | None = None,
    ) -> None:
        self.title = title
        self.transition = transition
        self.margin = margin
        self.content_max_width = content_max_width
        self.font_size = font_size
        self.line_height = line_height
        self.extra_css = extra_css
        if isinstance(theme, str):
            theme = [theme]
        self.themes: list[str] = list(theme) if theme else []
        self.theme_css: str = resolve_themes(self.themes) if self.themes else ""
        self._slides: list[SlideInfo] = []
        self._audio: list[dict] = []

    def audio(self, path: str | Path, *, at: float = 0.0) -> None:
        """Declare an audio bed mixed in at render time.

        Not part of the timeline's visual state: seek() ignores it entirely,
        and interactive playback is silent. Only rendering consumes it.
        """
        self._audio.append({"src": str(path), "at": at})

    def theme_style_block(self) -> str:
        """Render the full theme override as an HTML <style> block.

        Order (last wins via cascade):
            1. resolved theme list (from ``theme=`` or CLI ``--theme``)
            2. per-deck variable overrides (margin, font_size, etc.)
            3. ``--aud-deck-title`` exposed for themes to use in ``content:``
            4. ``extra_css`` — most explicit, wins over everything
        """
        parts: list[str] = []
        if self.theme_css:
            parts.append(self.theme_css)
        vars_map = {
            "--aud-slide-padding": self.margin,
            "--aud-content-max-width": self.content_max_width,
            "--aud-font-size": self.font_size,
            "--aud-line-height": self.line_height,
        }
        decls = "\n".join(f"    {k}: {v};" for k, v in vars_map.items() if v)
        if decls:
            parts.append(f":root {{\n{decls}\n}}")
        parts.append(
            f":root {{ --aud-deck-title: {_css_string_literal(self.title)}; }}"
        )
        if self.transition is not None:
            parts.append(
                f":root {{ --aud-transition: {_resolve_transition(self.transition)}; }}"
            )
        if self.extra_css:
            parts.append(self.extra_css)
        return "<style>\n" + "\n\n".join(parts) + "\n</style>"

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

    def scene(
        self,
        func: Callable | None = None,
        *,
        order: float | None = None,
        title: str | None = None,
    ) -> Callable:
        """Register an async function as a scene.

        Identical registration to ``slide``; the difference is which context
        object the compiler passes in — a full SceneContext rather than the
        restricted slide shim.
        """
        def decorator(fn: Callable) -> Callable:
            fn._auditorium_scene = True
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
