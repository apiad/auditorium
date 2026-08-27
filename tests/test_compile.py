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
