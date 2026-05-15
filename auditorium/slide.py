from __future__ import annotations

import asyncio
import base64
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any

import markdown

if TYPE_CHECKING:
    from auditorium.server import Presentation


def _jupyter_to_html(obj: Any) -> str:
    """Render an object to HTML via the Jupyter display protocol.

    Strings pass through. Otherwise, priority order: ``_repr_html_``,
    ``_repr_svg_``, ``_repr_png_``, ``_repr_jpeg_``. Falls back to ``str(obj)``.
    PNG/JPEG bytes are wrapped in a base64 data-URI ``<img>``. Methods that
    return ``(data, metadata)`` tuples have the ``data`` element used.
    """
    if isinstance(obj, str):
        return obj

    def _unwrap(result: Any) -> Any:
        if isinstance(result, tuple) and len(result) == 2:
            return result[0]
        return result

    if hasattr(obj, "_repr_html_"):
        html = _unwrap(obj._repr_html_())
        if html is not None:
            return html

    if hasattr(obj, "_repr_svg_"):
        svg = _unwrap(obj._repr_svg_())
        if svg is not None:
            return svg

    for attr, mime in (("_repr_png_", "png"), ("_repr_jpeg_", "jpeg")):
        if hasattr(obj, attr):
            data = _unwrap(getattr(obj, attr)())
            if data is not None:
                if isinstance(data, str):
                    # Already base64-encoded (IPython convention when metadata is set).
                    b64 = data
                else:
                    b64 = base64.b64encode(data).decode("ascii")
                return f'<img src="data:image/{mime};base64,{b64}" alt="">'

    return str(obj)


class SlideContext:
    """Context object passed to each slide function, exposing the async vocabulary."""

    def __init__(self, pres: Presentation) -> None:
        self._pres = pres
        self._target_stack: list[str] = []

    # --- Content ---

    async def show(self, content: Any, *, element_id: str | None = None) -> None:
        """Append content to the current insertion target.

        Accepts any object. Strings are appended as HTML directly. Objects
        implementing the Jupyter display protocol (``_repr_html_``,
        ``_repr_svg_``, ``_repr_png_``, ``_repr_jpeg_``) are rendered via
        those methods — so matplotlib figures, pandas DataFrames, altair
        charts, tesserax canvases, IPython rich objects all work natively.
        Anything else falls back to ``str(content)``.
        """
        html = _jupyter_to_html(content)
        mutation: dict = {
            "action": "append",
            "html": f"<div>{html}</div>",
            "element_id": element_id,
        }
        if self._target_stack:
            mutation["target"] = f"#{self._target_stack[-1]}"
        await self._pres.send_mutation(mutation)

    async def hide(self, selector: str) -> None:
        """Remove an element from the DOM by CSS selector."""
        await self._pres.send_mutation({
            "action": "remove",
            "selector": selector,
        })

    async def replace(self, selector: str, html: str) -> None:
        """Replace the inner HTML of an element matched by selector."""
        await self._pres.send_mutation({
            "action": "replace",
            "selector": selector,
            "html": html,
        })

    async def set_class(self, selector: str, cls: str) -> None:
        """Add CSS class(es) to an element."""
        await self._pres.send_mutation({
            "action": "set_class",
            "selector": selector,
            "cls": cls,
        })

    async def remove_class(self, selector: str, cls: str) -> None:
        """Remove CSS class(es) from an element."""
        await self._pres.send_mutation({
            "action": "remove_class",
            "selector": selector,
            "cls": cls,
        })

    # --- Markdown ---

    async def md(self, text: str, *, element_id: str | None = None) -> None:
        """Render markdown text and append it."""
        html = markdown.markdown(
            textwrap.dedent(text).strip(),
            extensions=["fenced_code", "tables"],
        )
        await self.show(html, element_id=element_id)

    async def show_md(self, path: str | Path, *, element_id: str | None = None) -> None:
        """Load a markdown file and render it."""
        text = Path(path).read_text()
        await self.md(text, element_id=element_id)

    # --- Semantic chrome ---

    async def title(self, text: str) -> None:
        """Render the slide title.

        Semantic equivalent of ``md('# text')`` but emits an element with
        ``class="aud-slide-title"`` so themes can target it for chrome,
        decoration, or running-head injection.
        """
        mutation: dict = {
            "action": "append",
            "html": f'<h1 class="aud-slide-title">{text}</h1>',
        }
        if self._target_stack:
            mutation["target"] = f"#{self._target_stack[-1]}"
        await self._pres.send_mutation(mutation)

    async def subtitle(self, text: str) -> None:
        """Render the slide subtitle as an ``<h2>`` with class ``aud-slide-subtitle``."""
        mutation: dict = {
            "action": "append",
            "html": f'<h2 class="aud-slide-subtitle">{text}</h2>',
        }
        if self._target_stack:
            mutation["target"] = f"#{self._target_stack[-1]}"
        await self._pres.send_mutation(mutation)

    # --- Info / academic blocks ---

    _BLOCK_KINDS = {
        # generic info
        "note": "Note",
        "info": "Info",
        "success": "Success",
        "warning": "Warning",
        "error": "Error",
        "tip": "Tip",
        # academic
        "definition": "Definition",
        "theorem": "Theorem",
        "lemma": "Lemma",
        "corollary": "Corollary",
        "proof": "Proof",
        "example": "Example",
        "remark": "Remark",
        "quote": "Quote",
    }

    async def block(
        self,
        kind: str,
        body: str,
        *,
        title: str | None = None,
    ) -> None:
        """Render a styled information / academic block.

        Kinds: ``note``, ``info``, ``success``, ``warning``, ``error``, ``tip``,
        ``definition``, ``theorem``, ``lemma``, ``corollary``, ``proof``,
        ``example``, ``remark``, ``quote``.

        ``body`` is rendered as markdown. ``title`` overrides the default
        label (e.g. pass ``title="Lemma 1.2 (Convergence)"``).
        """
        if kind not in self._BLOCK_KINDS:
            raise ValueError(
                f"unknown block kind {kind!r}; "
                f"expected one of {sorted(self._BLOCK_KINDS)}"
            )
        label = title if title is not None else self._BLOCK_KINDS[kind]
        body_html = markdown.markdown(
            textwrap.dedent(body).strip(),
            extensions=["fenced_code", "tables"],
        )
        html = (
            f'<div class="aud-block aud-block-{kind}">'
            f'<div class="aud-block-title">{label}</div>'
            f'<div class="aud-block-body">{body_html}</div>'
            f'</div>'
        )
        mutation: dict = {"action": "append", "html": html}
        if self._target_stack:
            mutation["target"] = f"#{self._target_stack[-1]}"
        await self._pres.send_mutation(mutation)

    # --- Timing ---

    async def step(self) -> None:
        """Wait for a keypress to continue, or auto-advance if auto_step is set."""
        event = asyncio.Event()
        self._pres.step_event = event
        if self._pres.auto_step is not None:
            try:
                await asyncio.wait_for(event.wait(), timeout=self._pres.auto_step)
            except asyncio.TimeoutError:
                pass  # auto-advance
        else:
            await event.wait()
        # Signal step completion (for step-by-step export)
        await self._pres.send({"type": "step_complete"})

    async def sleep(self, seconds: float) -> None:
        """Pause for a duration. Instant when instant_sleep is set (export mode).

        When auto_step is None but instant_sleep is True (step-by-step export),
        sleep acts like step — blocks for a keypress so the exporter can capture
        the state before and after each sleep boundary.
        """
        if self._pres.instant_sleep:
            if self._pres.auto_step is None:
                # Step-by-step export: treat sleep as a capture boundary.
                # Send sleep_complete (not step_complete) so the exporter
                # knows this is a timed boundary with the original duration.
                # Set event BEFORE sending signal to avoid race with the
                # exporter's keypress arriving before step_event is set.
                event = asyncio.Event()
                self._pres.step_event = event
                await self._pres.send({"type": "sleep_complete", "duration": seconds})
                await event.wait()
            return
        await asyncio.sleep(seconds)

    # --- Layout ---

    async def columns(self, sizing: int | list[int | str] = 2):
        """Create a horizontal flex container with sub-regions.

        sizing: int for equal widths, list of int for ratios,
        or list with "auto" for natural-size columns (e.g. ["auto", 1]).
        """
        from auditorium.layout import columns
        return await columns(self, sizing)

    async def rows(self, sizing: int | list[int | str] = 2):
        """Create a vertical flex container with sub-regions.

        sizing: int for equal heights, list of int for ratios,
        or list with "auto" for fixed-size rows (e.g. ["auto", 1, "auto"]).
        The container fills its parent height.
        """
        from auditorium.layout import rows
        return await rows(self, sizing)

    async def place(self, html: str, x: int, y: int, *, element_id: str | None = None) -> None:
        """Absolutely position an element at pixel coordinates."""
        from auditorium.layout import place
        await place(self, html, x, y, element_id=element_id)
