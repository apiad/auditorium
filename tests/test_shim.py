import inspect

from auditorium.compile import compile_deck
from auditorium.deck import Deck
from auditorium.slide import SlideContext


async def test_step_becomes_a_beat():
    deck = Deck("D")

    @deck.slide
    async def one(ctx):
        await ctx.md("hello")
        await ctx.step()
        await ctx.md("world")

    tl = await compile_deck(deck)
    assert len(tl.beats) == 1


async def test_sleep_advances_the_clock_instead_of_blocking():
    import time
    deck = Deck("D")

    @deck.slide
    async def one(ctx):
        await ctx.sleep(5.0)
        await ctx.md("after")

    started = time.monotonic()
    tl = await compile_deck(deck)
    assert time.monotonic() - started < 0.5
    assert tl.ops[-1].t == 5000


async def test_shim_beats_get_a_nonzero_render_hold():
    """A slide deck rendered to video must not blast past its reveals."""
    deck = Deck("D")

    @deck.slide
    async def one(ctx):
        await ctx.step()

    tl = await compile_deck(deck)
    assert tl.beats[0].hold_ms == 1500


async def test_the_construction_vocabulary_is_unchanged():
    """These are timing-agnostic and must survive the rewrite verbatim."""
    expected = {
        "show", "md", "show_md", "title", "subtitle", "section", "block",
        "hide", "replace", "set_class", "remove_class",
        "columns", "rows", "place", "step", "sleep",
    }
    actual = {n for n, _ in inspect.getmembers(SlideContext, inspect.isfunction)
              if not n.startswith("_")}
    assert expected <= actual


async def test_the_export_fakery_is_gone():
    src = inspect.getsource(SlideContext)
    assert "instant_sleep" not in src
    assert "auto_step" not in src


async def test_every_vocabulary_method_actually_runs_and_emits():
    """Exercise the vocabulary, do not merely name it.

    The sibling name-check test cannot catch a broken method body: it asserts
    the attribute exists, which stays true while the call raises. layout.py
    kept calling a `_pres` attribute the shim no longer has, and the suite
    stayed green over `columns()`/`rows()`/`place()` raising AttributeError.
    This test drives each method through a real compile instead.
    """
    deck = Deck("Vocabulary")

    @deck.slide
    async def everything(ctx):
        await ctx.title("T")
        await ctx.subtitle("S")
        await ctx.section("Sec", number="01")
        await ctx.md("**bold**")
        await ctx.show("<p>raw</p>")
        await ctx.block("note", "body text")
        await ctx.place("<p>placed</p>", 10, 20)
        await ctx.set_class("#slide-root", "x")
        await ctx.remove_class("#slide-root", "x")
        await ctx.replace("#slide-root", "<p>new</p>")
        await ctx.hide("#slide-root")

        left, right = await ctx.columns([2, 1])
        async with left:
            await ctx.md("left")
        async with right:
            await ctx.md("right")

        header, body, footer = await ctx.rows(["auto", 1, "auto"])
        async with body:
            await ctx.md("body")

    tl = await compile_deck(deck)
    actions = [o.action for o in tl.ops]
    assert "append" in actions
    assert "set_class" in actions
    assert "remove_class" in actions
    assert "replace" in actions
    assert "remove" in actions
    assert len(tl.ops) >= 15


async def test_region_scoping_nests_content_under_its_container():
    """`async with region` must set the emitted op's parent, not just push a stack."""
    deck = Deck("Nesting")

    @deck.slide
    async def nested(ctx):
        left, right = await ctx.columns(2)
        async with left:
            await ctx.md("inside")

    tl = await compile_deck(deck)
    parents = {n.parent for n in tl.nodes}
    assert parents != {"root"}, "region content was emitted at the root, not inside the column"
    assert any(p.startswith("cols-") for p in parents)
