"""Auditorium 4.0 — a demo you watch, not a deck you click through.

Every scene here moves. That is the point: 4.0 compiles a timeline instead of
performing one, so an authoring script is ordinary Python and the animation is
whatever that Python decides. The bubble sort below is a real bubble sort —
its inner loop calls `play()`, and every swap you see is a swap it made.

    auditorium run     examples/demo.py     # present it
    auditorium preview examples/demo.py     # scrub it
    auditorium render  examples/demo.py -o demo.mp4

Authored for 1920x1080. Translations are in CSS pixels, so the geometry below
assumes that stage; render or preview at another size and the motion scales
with it but the hand-tuned offsets do not.
"""

from auditorium import Deck
from auditorium.nodes import Arrow, Circle, Line

deck = Deck(
    "Auditorium 4.0",
    theme=["simple", "light"],
    content_max_width="1560px",
    margin="3rem",
)

# Eight equal columns of 181px with a 16px gap, inside the content width above.
# Measured at 1920x1080 rather than guessed, because the sort depends on it
# exactly: a bar translated by PITCH lands in its neighbour's slot, and a bar
# translated by PITCH minus a few pixels lands visibly nowhere.
PITCH = 197

# A top-level rows()/columns() switches the slide root out of centred mode into
# fill mode, and the columns container then collapses to its content height and
# sits at the top of the frame. Measured: the body row is 883px tall while the
# columns inside it were 120px. So every scene that uses a layout gives its
# content an explicit stage height and centres within that.
STAGE = 820

# Time to actually look at what just happened. wait() rather than beat(hold=)
# on purpose: a wait is real timeline duration, so it is identical in the
# render, in the preview scrubber and in live playback. A beat hold only
# dwells when rendering, which makes the preview's duration disagree with the
# video's -- the same split that made the frame counter lie.
BEAT = 1.6
READ = 2.6

INK = "#0f172a"
BLUE = "#2563eb"
RED = "#dc2626"

VALUES = [5, 2, 8, 1, 9, 3, 7, 4]


def bar(value: int, peak: int = 9) -> str:
    """A column of the sort: a proportional bar sitting on a shared baseline."""
    height = int(120 + (value / peak) * 520)
    return (
        f"<div style='height:{STAGE}px;display:flex;flex-direction:column;"
        "justify-content:flex-end;align-items:center;gap:0.6rem'>"
        f"<div style='width:100%;height:{height}px;border-radius:12px 12px 0 0;"
        f"background:linear-gradient(180deg,#60a5fa,{BLUE})'></div>"
        f"<span style='font:600 1.5rem ui-monospace,monospace;color:{INK}'>{value}</span>"
        "</div>"
    )


def card(label: str, tint: str) -> str:
    """A labelled box, pushed to mid-stage by its own margin.

    Two things this deliberately does NOT do, both learned by measuring.

    It is not wrapped in a centring div: show() hands back a handle to the
    outer element, so a wrapper would make `box.right` resolve to the edge of
    an invisible full-column box and the arrows would point into empty space.

    And it carries no max-width. show() already wraps whatever you give it in
    a div of its own, and the handle refers to THAT wrapper -- so a narrower
    card inside a full-width wrapper anchors to the wrapper, not to the card.
    Measured: the arrows landed 78px off, exactly the gap between the card
    edge and the column edge. Anything you intend to anchor to has to fill
    its wrapper.
    """
    return (
        f"<div style='margin-top:{(STAGE - 90) // 2}px;"
        f"background:#fff;border:2px solid {tint};border-radius:16px;"
        f"padding:1.6rem 2rem;text-align:center;"
        f"font:600 1.7rem ui-monospace,monospace;"
        f"color:{tint};box-shadow:0 8px 24px rgba(15,23,42,.10)'>{label}</div>"
    )


def centred(inner: str) -> str:
    """Wrap content so it sits in the middle of the stage rather than its top."""
    return (
        f"<div style='height:{STAGE}px;display:flex;align-items:center;"
        f"justify-content:center'>{inner}</div>"
    )


# --- 1. Opening --------------------------------------------------------

@deck.scene(title="Opening")
async def opening(s):
    """Open on motion, not on a bullet list."""
    title = await s.show(
        f"<div style='font:800 6rem Playfair Display,Georgia,serif;color:{INK};"
        "letter-spacing:-.02em'>Auditorium 4.0</div>"
    )
    rule = await s.draw(Line(from_=(660, 620), to=(1260, 620), stroke=BLUE, width=6))
    tag = await s.show(
        "<div style='font:400 2.1rem Source Serif 4,Georgia,serif;color:#475569;"
        "margin-top:1.2rem'>A timeline you can seek, render, and scrub.</div>"
    )

    await s.play(title.animate.fade_in(), run_time=0.7, ease="out-cubic")
    await s.play(rule.animate.draw_on(), run_time=0.7, ease="out-cubic")
    await s.play(tag.animate.fade_in(), run_time=0.6)
    await s.wait(BEAT)
    await s.beat()


# --- 2. The idea -------------------------------------------------------

@deck.scene(title="Compile, don't perform")
async def thesis(s):
    """The one architectural claim, shown rather than asserted."""
    header, body = await s.rows(["auto", 1])
    async with header:
        await s.title("Your Python runs first")
        await s.subtitle("play() records a track and returns. Nothing sleeps.")

    async with body:
        left, right = await s.columns([1, 1])
        async with left:
            code = await s.show(
                centred("<pre style='text-align:left;font:500 1.35rem ui-monospace,monospace;"
                "background:#0f172a;color:#e2e8f0;padding:1.6rem;border-radius:14px;"
                "line-height:1.7'><code>for i in range(n):\n"
                "    for j in range(n - i - 1):\n"
                "        if a[j] > a[j+1]:\n"
                "            swap(a, j, j+1)\n"
                "            <span style='color:#fbbf24'>await s.play(...)</span>"
                "</code></pre>")
            )
        async with right:
            note = await s.show(
                centred("<div style='font:400 1.9rem Source Serif 4,Georgia,serif;color:#334155;"
                "line-height:1.6;text-align:left'>The loop is ordinary Python.<br>"
                "It runs to completion <em>before</em> anything is displayed, so loops, "
                "recursion and numpy all work — and the result is a timeline you can "
                "seek to any instant.</div>")
            )

    await s.play(code.animate.fade_in(), run_time=0.6)
    await s.play(note.animate.fade_in(), run_time=0.6)
    await s.wait(READ)
    await s.beat()


# --- 3. The sort -------------------------------------------------------

@deck.scene(title="A real bubble sort")
async def sorting(s):
    """The centrepiece: Python decides the animation, frame by frame.

    Nothing here is choreographed. The loop sorts a list; each swap it
    performs emits one `play()`, so the motion on screen is the algorithm's
    own behaviour rather than a reenactment of it.
    """
    header, body = await s.rows(["auto", 1])
    async with header:
        await s.title("Watch it sort")
        await s.subtitle("Every swap below is one the algorithm actually made.")

    bars = []
    async with body:
        cols = await s.columns(len(VALUES))
        for column, value in zip(cols, VALUES):
            async with column:
                bars.append(await s.show(bar(value)))

    await s.play(*[b.animate.fade_in() for b in bars], run_time=0.6, lag=0.07)
    await s.wait(1.0)
    await s.beat()

    # move_by composites additively, so each call moves a bar BY one slot
    # rather than to an absolute position -- which is exactly what a sequence
    # of swaps needs.
    order = list(VALUES)
    slots = list(bars)
    for i in range(len(order)):
        for j in range(len(order) - i - 1):
            if order[j] > order[j + 1]:
                order[j], order[j + 1] = order[j + 1], order[j]
                await s.play(
                    slots[j].animate.move_by(PITCH, 0),
                    slots[j + 1].animate.move_by(-PITCH, 0),
                    run_time=0.26,
                    ease="out-cubic",
                )
                slots[j], slots[j + 1] = slots[j + 1], slots[j]

    # Hold on the sorted result: the payoff is the last frame, not the motion.
    await s.wait(2.0)
    await s.beat()


# --- 4. Anchors --------------------------------------------------------

@deck.scene(title="Arrows that follow")
async def anchors(s):
    """Geometry whose endpoints are promises, not coordinates."""
    header, body = await s.rows(["auto", 1])
    async with header:
        await s.title("Arrows that follow")
        await s.subtitle("An anchor is symbolic. Python never computes where anything is.")

    boxes = []
    async with body:
        cols = await s.columns(3)
        for column, (label, tint) in zip(
            cols, [("compile", BLUE), ("seek(t)", INK), ("render", RED)]
        ):
            async with column:
                boxes.append(await s.show(card(label, tint)))

    await s.play(*[b.animate.fade_in() for b in boxes], run_time=0.5, lag=0.12)

    first = await s.draw(Arrow(from_=boxes[0].right, to=boxes[1].left, stroke=BLUE, width=4))
    second = await s.draw(Arrow(from_=boxes[1].right, to=boxes[2].left, stroke=RED, width=4))
    await s.play(first.animate.draw_on(), second.animate.draw_on(), run_time=0.7, lag=0.25)
    await s.wait(1.2)
    await s.beat()

    # The arrows were never told where the box is -- they re-resolve every
    # frame, so they stay attached while it moves.
    await s.play(boxes[1].animate.move_by(0, -170), run_time=0.9, ease="out-back")
    await s.wait(1.4)
    await s.beat()
    await s.play(boxes[1].animate.move_by(0, 170), run_time=0.7, ease="out-cubic")
    await s.wait(BEAT)


# --- 5. Stagger --------------------------------------------------------

@deck.scene(title="Overlap")
async def overlap(s):
    """One play(), many animations, staggered — what a timeline buys."""
    header, body = await s.rows(["auto", 1])
    async with header:
        await s.title("One play(), many animations")
        await s.subtitle("lag= staggers their starts. Reveals cannot express this.")

    dots = []
    async with body:
        cols = await s.columns(10)
        for i, column in enumerate(cols):
            async with column:
                dots.append(await s.show(centred(
                    f"<div style='width:86px;height:86px;border-radius:50%;"
                    f"background:{BLUE};opacity:.9'></div>"
                )))

    await s.play(*[d.animate.fade_in() for d in dots], run_time=0.5, lag=0.06)
    await s.play(*[d.animate.move_by(0, -130) for d in dots],
                 run_time=0.5, ease="out-cubic", lag=0.05)
    await s.play(*[d.animate.move_by(0, 130) for d in dots],
                 run_time=0.5, ease="out-cubic", lag=0.05)
    await s.wait(BEAT)
    await s.beat()


# --- 6. Close ----------------------------------------------------------

@deck.scene(title="Close")
async def close(s):
    """Land it."""
    title = await s.show(
        f"<div style='font:800 4.6rem Playfair Display,Georgia,serif;color:{INK}'>"
        "Same timeline, four surfaces</div>"
    )
    line = await s.show(
        "<div style='font:400 1.9rem Source Serif 4,Georgia,serif;color:#475569;"
        "margin-top:1.4rem'>present · preview · presenter · render — all of them "
        "<code>seek(t)</code></div>"
    )
    dot = await s.draw(Circle(at=(960, 830), r=13, stroke=RED, width=5))
    rule = await s.draw(Line(from_=(430, 830), to=(1490, 830), stroke="#cbd5e1", width=3))

    await s.play(title.animate.fade_in(), run_time=0.6, ease="out-cubic")
    await s.play(line.animate.fade_in(), run_time=0.5)
    await s.play(rule.animate.draw_on(), run_time=0.8)
    await s.play(dot.animate.fade_in(), run_time=0.4)
    await s.play(dot.animate.move_by(430, 0), run_time=1.2, ease="in-out")
    await s.wait(READ)
    await s.beat()
