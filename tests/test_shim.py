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
