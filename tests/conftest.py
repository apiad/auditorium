import pytest
import pytest_asyncio

from auditorium.testing import chromium_path


@pytest_asyncio.fixture
async def browser_page():
    playwright = pytest.importorskip("playwright.async_api")
    async with playwright.async_playwright() as p:
        kwargs = {}
        path = chromium_path()
        if path:
            kwargs["executable_path"] = path
        browser = await p.chromium.launch(**kwargs)
        context = await browser.new_context(viewport={"width": 800, "height": 600})
        page = await context.new_page()
        yield page
        await context.close()
        await browser.close()
