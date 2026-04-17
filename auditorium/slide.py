from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import markdown

if TYPE_CHECKING:
    from auditorium.server import Session


class SlideContext:
    """Context object passed to each slide function, exposing the async vocabulary."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._target_stack: list[str] = []

    # --- Content ---

    async def show(self, html: str, *, element_id: str | None = None) -> None:
        """Append HTML content to the current insertion target."""
        mutation: dict = {
            "action": "append",
            "html": f"<div>{html}</div>",
            "element_id": element_id,
        }
        if self._target_stack:
            mutation["target"] = f"#{self._target_stack[-1]}"
        await self._session.send_mutation(mutation)

    async def hide(self, selector: str) -> None:
        """Remove an element from the DOM by CSS selector."""
        await self._session.send_mutation({
            "action": "remove",
            "selector": selector,
        })

    async def replace(self, selector: str, html: str) -> None:
        """Replace the inner HTML of an element matched by selector."""
        await self._session.send_mutation({
            "action": "replace",
            "selector": selector,
            "html": html,
        })

    async def set_class(self, selector: str, cls: str) -> None:
        """Add CSS class(es) to an element."""
        await self._session.send_mutation({
            "action": "set_class",
            "selector": selector,
            "cls": cls,
        })

    async def remove_class(self, selector: str, cls: str) -> None:
        """Remove CSS class(es) from an element."""
        await self._session.send_mutation({
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

    # --- Timing ---

    async def step(self) -> None:
        """Wait for a keypress to continue."""
        event = asyncio.Event()
        self._session.step_event = event
        await event.wait()

    async def sleep(self, seconds: float) -> None:
        """Pause for a duration."""
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
