from auditorium.compile import compile_deck
from auditorium.deck import Deck


async def test_compiles_an_empty_deck():
    deck = Deck("Empty")
    tl = await compile_deck(deck)
    assert tl.meta["title"] == "Empty"
    assert tl.ops == []


async def test_compiles_a_single_scene():
    deck = Deck("One")

    @deck.scene
    async def intro(s):
        h = await s.show("<p>hi</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)

    tl = await compile_deck(deck)
    assert len(tl.nodes) == 1
    assert tl.tracks[0].end == 500


async def test_scenes_are_laid_end_to_end_on_one_clock():
    deck = Deck("Two")

    @deck.scene
    async def first(s):
        await s.wait(1.0)

    @deck.scene
    async def second(s):
        h = await s.show("<p>b</p>")
        await s.play(h.animate.fade_in(), run_time=0.5)

    tl = await compile_deck(deck)
    # The scene boundary emits a beat at 1000, which advances the clock by 1ms.
    assert tl.ops[0].t == 1001
    assert (tl.tracks[0].start, tl.tracks[0].end) == (1001, 1501)


async def test_a_scene_boundary_emits_a_beat():
    deck = Deck("Two")

    @deck.scene
    async def first(s):
        await s.wait(1.0)

    @deck.scene
    async def second(s):
        await s.wait(1.0)

    tl = await compile_deck(deck)
    assert [b.t for b in tl.beats] == [1000]


async def test_python_computation_drives_the_timeline():
    """The point of compile-not-perform: real algorithms author animations."""
    deck = Deck("Sort")

    @deck.scene
    async def bubble(s):
        arr = [3, 1, 2]
        handles = [await s.show(f"<b>{v}</b>") for v in arr]
        for i in range(len(arr)):
            for j in range(len(arr) - i - 1):
                if arr[j] > arr[j + 1]:
                    arr[j], arr[j + 1] = arr[j + 1], arr[j]
                    await s.play(handles[j].animate.move_to(j * 50, 0), run_time=0.2)

    tl = await compile_deck(deck)
    assert len(tl.tracks) > 0
    assert tl.duration_ms > 0


async def test_a_scene_boundary_clears_the_stage():
    """Without a clear op the whole deck accumulates into one continuous DOM.

    The old protocol sent a `clear` message per slide; a timeline has no
    implicit boundary, so the compiler has to emit one.
    """
    deck = Deck("Two")

    @deck.scene
    async def first(s):
        await s.show("<p>a</p>")

    @deck.scene
    async def second(s):
        await s.show("<p>b</p>")

    tl = await compile_deck(deck)
    clears = [o for o in tl.ops if o.action == "clear"]
    assert len(clears) == 1


async def test_the_clear_lands_after_the_beat_not_on_it():
    """At the beat the outgoing scene must still be whole.

    If the clear shared the beat's millisecond, the stage would wipe while
    the presenter is still paused on it — the audience would watch the slide
    vanish before the keypress that is meant to move on.
    """
    deck = Deck("Two")

    @deck.scene
    async def first(s):
        await s.show("<p>a</p>")

    @deck.scene
    async def second(s):
        await s.show("<p>b</p>")

    tl = await compile_deck(deck)
    beat_t = tl.beats[0].t
    clear_t = next(o.t for o in tl.ops if o.action == "clear")
    assert clear_t > beat_t
