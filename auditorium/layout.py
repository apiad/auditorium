from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from auditorium.slide import SlideContext

# Sizing values:
#   int     → flex: N (grows proportionally)
#   "auto"  → flex: 0 0 auto (natural content size, no grow)
SizingItem = int | str
Sizing = int | list[SizingItem]


class Region:
    """A layout region that serves as an insertion target via `async with`."""

    def __init__(self, ctx: SlideContext, region_id: str) -> None:
        self._ctx = ctx
        self.id = region_id

    async def __aenter__(self) -> Region:
        self._ctx._target_stack.append(self.id)
        await self._ctx._session.send({
            "type": "mutation",
            "action": "push_target",
            "selector": f"#{self.id}",
            "id": str(uuid.uuid4()),
        })
        return self

    async def __aexit__(self, *exc) -> None:
        self._ctx._target_stack.pop()
        await self._ctx._session.send({
            "type": "mutation",
            "action": "pop_target",
            "id": str(uuid.uuid4()),
        })


def _flex_style(item: SizingItem) -> str:
    """Convert a sizing item to a CSS flex value."""
    if item == "auto":
        return "flex: 0 0 auto"
    return f"flex: {item}"


def _normalize_sizing(sizing: Sizing) -> list[SizingItem]:
    """Normalize sizing to a list of items."""
    if isinstance(sizing, int):
        return [1] * sizing
    return list(sizing)


async def _switch_to_layout_mode(ctx: SlideContext) -> None:
    """Switch slide root from centered mode to layout mode."""
    await ctx._session.send_mutation({
        "action": "set_class",
        "selector": "#slide-root",
        "cls": "aud-layout-mode",
    })


async def columns(ctx: SlideContext, sizing: Sizing = 2) -> list[Region]:
    """Create a horizontal flex container with sub-regions."""
    items = _normalize_sizing(sizing)
    container_id = f"cols-{uuid.uuid4().hex[:8]}"
    children_html = ""
    regions = []
    for i, item in enumerate(items):
        child_id = f"{container_id}-{i}"
        style = _flex_style(item)
        children_html += f'<div id="{child_id}" style="{style}; min-width: 0;" class="px-4"></div>'
        regions.append(Region(ctx, child_id))

    if not ctx._target_stack:
        await _switch_to_layout_mode(ctx)

    html = (
        f'<div id="{container_id}" style="display: flex; flex-direction: row; gap: 1rem; width: 100%;">'
        f'{children_html}</div>'
    )
    mutation: dict = {"action": "append", "html": html}
    if ctx._target_stack:
        mutation["target"] = f"#{ctx._target_stack[-1]}"
    await ctx._session.send_mutation(mutation)
    return regions


async def rows(ctx: SlideContext, sizing: Sizing = 2) -> list[Region]:
    """Create a vertical flex container with sub-regions."""
    items = _normalize_sizing(sizing)
    container_id = f"rows-{uuid.uuid4().hex[:8]}"
    children_html = ""
    regions = []
    for i, item in enumerate(items):
        child_id = f"{container_id}-{i}"
        style = _flex_style(item)
        children_html += f'<div id="{child_id}" style="{style}; min-height: 0;" class="py-2"></div>'
        regions.append(Region(ctx, child_id))

    if not ctx._target_stack:
        await _switch_to_layout_mode(ctx)

    html = (
        f'<div id="{container_id}" style="display: flex; flex-direction: column; gap: 0.5rem; width: 100%; flex: 1; min-height: 0;">'
        f'{children_html}</div>'
    )
    mutation: dict = {"action": "append", "html": html}
    if ctx._target_stack:
        mutation["target"] = f"#{ctx._target_stack[-1]}"
    await ctx._session.send_mutation(mutation)
    return regions


async def place(ctx: SlideContext, html: str, x: int, y: int, *, element_id: str | None = None) -> None:
    """Absolutely position an element at pixel coordinates."""
    eid = element_id or f"placed-{uuid.uuid4().hex[:8]}"
    full_html = f'<div id="{eid}" style="position: absolute; left: {x}px; top: {y}px;">{html}</div>'
    await ctx._session.send_mutation({"action": "append", "html": full_html})
