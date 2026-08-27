async def test_chromium_launches_and_evaluates(browser_page):
    await browser_page.set_content("<div id='x'>hello</div>")
    text = await browser_page.evaluate("() => document.getElementById('x').textContent")
    assert text == "hello"


async def test_web_animations_api_available(browser_page):
    await browser_page.set_content("<div id='x'></div>")
    ok = await browser_page.evaluate(
        "() => typeof document.getAnimations === 'function'"
    )
    assert ok is True


async def test_animation_currenttime_is_settable(browser_page):
    """The bet the whole engine rests on: a paused animation can be seeked.

    If this fails, seek(t) is not implementable on WAAPI and the design needs
    the per-frame JS fallback instead.
    """
    await browser_page.set_content("<div id='x'>box</div>")
    opacity = await browser_page.evaluate(
        """() => {
            const el = document.getElementById('x');
            const anim = el.animate(
                [{ opacity: 0 }, { opacity: 1 }],
                { duration: 1000, fill: 'both' }
            );
            anim.pause();
            anim.currentTime = 500;
            return parseFloat(getComputedStyle(el).opacity);
        }"""
    )
    assert 0.4 < opacity < 0.6
