"""Auditorium 4.0 — a demo you watch, not a deck you click through.

Every scene moves, and two of them do mathematics. 4.0 compiles a timeline
instead of performing one, so an authoring script is ordinary Python: the
bubble sort's inner loop calls `play()`, and the Fourier scene computes every
partial sum before a single frame is drawn.

    auditorium run     examples/demo.py     # present it
    auditorium preview examples/demo.py     # scrub it
    auditorium render  examples/demo.py -o demo.mp4

Authored for 1920x1080. Translations and plot coordinates are CSS pixels, so
the geometry below assumes that stage.

Two gotchas worth knowing before editing, both of which cost real time to find:

  * `show()` wraps content in a div and the handle refers to THAT wrapper, so
    anything you anchor to has to fill its wrapper.
  * A top-level `rows()`/`columns()` drops the slide root out of centred mode
    and the columns container collapses to content height at the top of the
    frame, so scenes give their content an explicit stage height.
"""

import math

from auditorium import Deck
from auditorium.nodes import Arrow, Circle, Line, Path

deck = Deck(
    "Auditorium 4.0",
    theme=["minimalist", "dark"],
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

VALUES = [5, 2, 8, 1, 9, 3, 7, 4]

# --- The plot box, in stage pixels -------------------------------------
# Geometry is placed by hand because the SVG overlay does not negotiate with
# DOM layout: a curve drawn where text happens to be runs straight through it.
# These constants keep every figure clear of the title block.
PLOT_L, PLOT_R = 300, 1620
PLOT_MID = 690
PLOT_AMP = 200


def to_px(x, y, x0, x1):
    """Map maths coordinates into the plot box. Data, not layout."""
    px = PLOT_L + (x - x0) / (x1 - x0) * (PLOT_R - PLOT_L)
    return px, PLOT_MID - y * PLOT_AMP


def polyline(fn, x0, x1, samples=240):
    """An SVG path through fn, sampled evenly.

    This is the manim move: Python computes the geometry at compile time and
    the browser draws it on. No frame is rendered while this runs.
    """
    pts = []
    for i in range(samples + 1):
        x = x0 + (x1 - x0) * i / samples
        px, py = to_px(x, fn(x), x0, x1)
        pts.append(f"{px:.1f},{py:.1f}")
    return "M" + " L".join(pts)


def centred(inner: str) -> str:
    """Wrap content so it sits in the middle of the stage rather than its top."""
    return (
        f"<div style='height:{STAGE}px;display:flex;align-items:flex-start;"
        f"justify-content:center;padding-top:2rem'>{inner}</div>"
    )


def bar(value: int, peak: int = 9) -> str:
    """A column of the sort: a proportional bar sitting on a shared baseline."""
    height = int(120 + (value / peak) * 520)
    return (
        f"<div style='height:{STAGE}px;display:flex;flex-direction:column;"
        "justify-content:flex-end;align-items:center;gap:0.6rem'>"
        f"<div style='width:100%;height:{height}px;border-radius:12px 12px 0 0;"
        "background:linear-gradient(180deg,var(--aud-geom-2),var(--aud-geom-1))'></div>"
        "<span style='font:600 1.5rem ui-monospace,monospace'>"
        f"{value}</span></div>"
    )


# --- 1. Opening --------------------------------------------------------

@deck.scene(title="Opening")
async def opening(s):
    """Open on motion, not on a bullet list."""
    title = await s.show(
        "<div style='font:200 6rem Inter,system-ui,sans-serif;"
        "letter-spacing:-.03em'>Auditorium <b style='font-weight:600'>4.0</b></div>"
    )
    rule = await s.draw(Line(from_=(660, 620), to=(1260, 620), width=5))
    tag = await s.show(
        "<div style='font:300 2.1rem Inter,system-ui,sans-serif;"
        "color:var(--aud-muted);margin-top:1.4rem'>"
        "Animation and video, authored in Python.</div>"
    )

    await s.play(title.animate.fade_in(), run_time=0.7, ease="out-cubic")
    await s.play(rule.animate.draw_on(), run_time=0.7, ease="out-cubic")
    await s.play(tag.animate.fade_in(), run_time=0.6)
    await s.wait(BEAT)
    await s.beat()


# --- 2. Fourier --------------------------------------------------------

# The wheel: arm k turns at frequency 2k+1 with radius proportional to
# 1/(2k+1), and the tip traces a square wave. Four arms is where the shape
# becomes unmistakable while each circle is still individually readable.
HARMONICS = 4
WHEEL_X, WHEEL_Y = 450, 690      # centre of the wheel, on the trace's axis
WHEEL_R = 175
TURNS = 2


def arm(radius: float, series: int, parent_radius: float, root: bool = False) -> str:
    """One epicycle arm: a spoke, its circle, and a hub at the far end.

    Positioned at its parent's tip and rotating about its own origin, so
    nesting arm k+1 inside arm k composes the rotations -- which is the
    entire mechanism. transform-origin is 0 0 rather than the default centre,
    because an arm pivots at its root, not at its middle.
    """
    # The root arm is fixed to the stage so its centre is a known point in the
    # same pixel space as the SVG trace; every arm after it is absolute inside
    # its parent, which is what makes the rotations compose.
    place = (
        f"position:fixed;left:{WHEEL_X}px;top:{WHEEL_Y}px" if root
        else f"position:absolute;left:{parent_radius:.1f}px;top:0"
    )
    return (
        f"<div style='{place};"
        "width:0;height:0;transform-origin:0 0'>"
        f"<div style='position:absolute;left:{-radius:.1f}px;top:{-radius:.1f}px;"
        f"width:{2 * radius:.1f}px;height:{2 * radius:.1f}px;border-radius:50%;"
        "border:1px solid var(--aud-geom-muted);opacity:.75'></div>"
        f"<div style='position:absolute;left:0;top:-1.5px;width:{radius:.1f}px;"
        f"height:3px;background:var(--aud-geom-{series})'></div>"
        f"<div style='position:absolute;left:{radius - 6:.1f}px;top:-6px;"
        "width:12px;height:12px;border-radius:50%;"
        f"background:var(--aud-geom-{series})'></div>"
        "</div>"
    )


@deck.scene(title="Fourier")
async def fourier(s):
    """The centrepiece: the machine that makes the wave, not the wave.

    Four nested arms turn at 1, 3, 5 and 7 times the base frequency with
    radii 1, 1/3, 1/5, 1/7 -- the Fourier coefficients of a square wave, as
    rotation. Their tip traces the curve drawn alongside, and the Gibbs
    overshoot appears at the corners because the mathematics puts it there.

    Nothing here is keyframed. Python computes the trace, and the arms are
    four `rotate_by` calls in one `play()`.
    """
    header, body = await s.rows(["auto", 1])
    async with header:
        await s.title("A square wave, drawn by rotation")
        await s.subtitle("Four arms turning at 1, 3, 5 and 7 times the base frequency.")

    x0, x1 = 0.0, TURNS * 2 * math.pi

    def partial(x):
        return 4 / math.pi * sum(
            math.sin((2 * k + 1) * x) / (2 * k + 1) for k in range(HARMONICS)
        )

    async with body:
        stage = await s.show(
            "<div style='position:relative;width:100%;height:620px'></div>"
        )

    # The wheel, nested arm inside arm: each one's rotation composes onto its
    # parent's, which is the entire mechanism.
    radii = [WHEEL_R / (2 * k + 1) for k in range(HARMONICS)]
    arms, parent = [], stage
    for k, radius in enumerate(radii):
        parent_radius = radii[k - 1] if k else 0.0
        parent = await s.show(
            arm(radius, 1 + (k % 2), parent_radius, root=(k == 0)), into=parent
        )
        arms.append(parent)

    # The trace, to the right of the wheel and on the same vertical scale.
    trace_l = WHEEL_X + WHEEL_R + 140
    curve = await s.draw(Path(
        "M" + " L".join(
            f"{trace_l + (x - x0) / (x1 - x0) * (PLOT_R - trace_l):.1f},"
            f"{PLOT_MID - partial(x) * WHEEL_R * 0.72:.1f}"
            for x in (x0 + (x1 - x0) * i / 600 for i in range(601))
        ),
        series=1, width=4,
    ))
    axis = await s.draw(Line(from_=(trace_l, PLOT_MID), to=(PLOT_R, PLOT_MID),
                             muted=True, width=2))

    await s.play(*[a.animate.fade_in() for a in arms], run_time=0.6, lag=0.12)
    await s.play(axis.animate.draw_on(), run_time=0.4)
    await s.wait(0.4)

    # One play(): every arm turns, and the trace draws, over the same span.
    spin = 4.6
    await s.play(
        *[a.animate.rotate_by(360 * TURNS * (2 * k + 1)) for k, a in enumerate(arms)],
        curve.animate.draw_on(),
        run_time=spin,
    )

    await s.wait(READ)
    await s.beat()


# --- 3. Newton ---------------------------------------------------------

@deck.scene(title="Newton")
async def newton(s):
    """Tangent lines walking to a root, placed by the actual iteration."""
    header, body = await s.rows(["auto", 1])
    async with header:
        await s.title("Newton's method, actually iterating")

    def f(x):
        return x ** 3 - 2 * x - 5

    def df(x):
        return 3 * x ** 2 - 2

    # A narrow window with a low divisor: over [1.9, 3.0] the cubic climbs from
    # -2.1 to 16, so dividing by 8 fills the plot box and the curvature is
    # actually visible. Squashed flatter, tangents and curve are the same line.
    x0, x1 = 1.9, 3.0
    scale = 8.0

    async with body:
        rule = await s.show(centred(
            r"<div>$\displaystyle x_{n+1}=x_n-\frac{f(x_n)}{f'(x_n)}"
            r"\qquad f(x)=x^{3}-2x-5$</div>"
        ))

    axis = await s.draw(Line(from_=(PLOT_L, PLOT_MID), to=(PLOT_R, PLOT_MID),
                             muted=True, width=2))
    curve = await s.draw(Path(polyline(lambda x: f(x) / scale, x0, x1),
                              series=1, width=5))

    await s.play(rule.animate.fade_in(), run_time=0.5)
    await s.play(axis.animate.draw_on(), run_time=0.4)
    await s.play(curve.animate.draw_on(), run_time=0.9, ease="out-cubic")
    await s.wait(0.5)

    # The iteration decides the geometry. Nothing here is choreographed: these
    # are the actual iterates of x^3 - 2x - 5 from x0 = 2.9.
    x = 2.95
    for _ in range(3):
        nxt = x - f(x) / df(x)
        ax, ay = to_px(x, f(x) / scale, x0, x1)
        bx, by = to_px(nxt, 0.0, x0, x1)
        drop = await s.draw(Line(from_=(ax, ay), to=(ax, PLOT_MID),
                                 muted=True, width=2, dash="0.03 0.03"))
        tangent = await s.draw(Line(from_=(ax, ay), to=(bx, by), series=2, width=4))
        mark = await s.draw(Circle(at=(bx, by), r=11, series=3, width=4))
        await s.play(drop.animate.draw_on(), run_time=0.35)
        await s.play(tangent.animate.draw_on(), run_time=0.55, ease="out-cubic")
        await s.play(mark.animate.fade_in(), run_time=0.3)
        await s.wait(0.55)
        x = nxt

    await s.wait(READ)
    await s.beat()


# --- 4. The sort -------------------------------------------------------

@deck.scene(title="A real bubble sort")
async def sorting(s):
    """Python decides the animation, swap by swap."""
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

    # move_by composites additively, so each call moves a bar BY one slot --
    # which is exactly what a sequence of swaps needs.
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


# --- 5. Anchors --------------------------------------------------------

@deck.scene(title="Arrows that follow")
async def anchors(s):
    """Geometry whose endpoints are promises, not coordinates.

    Six nodes, seven edges, and not one coordinate in this function. Every
    edge names a *side of a node* and the browser resolves it on every frame,
    so when the graph is shoved around the edges follow without anything
    recomputing them. A single arrow between two boxes would demonstrate the
    API; a graph that survives being jostled demonstrates the feature.
    """
    header, body = await s.rows(["auto", 1])
    async with header:
        await s.title("Arrows that follow")
        await s.subtitle("An anchor is symbolic. Python never computes where anything is.")

    def node(label, series):
        # Fills its column on purpose. show() wraps content in a div and the
        # handle refers to THAT wrapper, so a narrower box would anchor to the
        # column edge and every edge would end in empty space.
        return (
            "<div style='margin:110px 0;"
            f"border:2px solid var(--aud-geom-{series});border-radius:14px;"
            "padding:1.1rem 0.8rem;text-align:center;"
            "font:500 1.35rem ui-monospace,monospace;"
            f"color:var(--aud-geom-{series})'>{label}</div>"
        )

    # Row 1 is the compile path, row 2 the surfaces that consume it. Which is
    # what the architecture actually is, so the graph is not decoration.
    top_labels = [("deck.py", 4), ("compile", 1), ("timeline", 1)]
    bottom_labels = [("present", 2), ("seek(t)", 3), ("render", 2)]

    top, bottom = [], []
    async with body:
        row_a, row_b = await s.rows(2)
        async with row_a:
            cols = await s.columns(3)
            for column, (label, series) in zip(cols, top_labels):
                async with column:
                    top.append(await s.show(node(label, series)))
        async with row_b:
            cols = await s.columns(3)
            for column, (label, series) in zip(cols, bottom_labels):
                async with column:
                    bottom.append(await s.show(node(label, series)))

    deck_py, compile_, timeline = top
    present, seek, render = bottom

    await s.play(*[n.animate.fade_in() for n in top + bottom],
                 run_time=0.5, lag=0.06)

    edges = [
        await s.draw(Arrow(from_=deck_py.right, to=compile_.left, series=4, width=3)),
        await s.draw(Arrow(from_=compile_.right, to=timeline.left, series=1, width=3)),
        await s.draw(Arrow(from_=timeline.bottom, to=seek.top, series=1, width=3)),
        await s.draw(Arrow(from_=seek.left, to=present.right, series=3, width=3)),
        await s.draw(Arrow(from_=seek.right, to=render.left, series=3, width=3)),
    ]
    await s.play(*[e.animate.draw_on() for e in edges], run_time=0.8, lag=0.08)
    await s.wait(1.4)
    await s.beat()

    # Shove the whole graph around. Nothing below touches an edge -- only the
    # nodes move, and the seven edges keep up because they were never told
    # where anything was.
    await s.play(
        timeline.animate.move_by(0, -120),
        compile_.animate.move_by(40, 70),
        seek.animate.move_by(-70, 60),
        render.animate.move_by(90, -40),
        run_time=0.9, ease="out-back", lag=0.07,
    )
    await s.wait(1.2)

    await s.play(
        deck_py.animate.move_by(0, 90),
        present.animate.move_by(-60, -80),
        timeline.animate.move_by(120, 60),
        seek.animate.move_by(60, -110),
        run_time=0.9, ease="out-back", lag=0.07,
    )
    await s.wait(1.2)

    # And back. move_by is a delta, so the returns are just the negatives.
    await s.play(
        timeline.animate.move_by(-120, 60),
        compile_.animate.move_by(-40, -70),
        seek.animate.move_by(10, 50),
        render.animate.move_by(-90, 40),
        deck_py.animate.move_by(0, -90),
        present.animate.move_by(60, 80),
        run_time=0.8, ease="out-cubic", lag=0.05,
    )
    await s.wait(BEAT)
    await s.beat()


# --- 6. Close ----------------------------------------------------------

@deck.scene(title="Close")
async def close(s):
    """Land it."""
    title = await s.show(
        "<div style='font:200 4.6rem Inter,system-ui,sans-serif;"
        "letter-spacing:-.02em'>Same timeline, four surfaces</div>"
    )
    line = await s.show(
        "<div style='font:300 1.9rem Inter,system-ui,sans-serif;"
        "color:var(--aud-muted);margin-top:1.4rem'>present · preview · presenter "
        "· render — all of them <code>seek(t)</code></div>"
    )
    rule = await s.draw(Line(from_=(430, 830), to=(1490, 830), muted=True, width=3))
    dot = await s.draw(Circle(at=(430, 830), r=13, series=2, width=5))

    await s.play(title.animate.fade_in(), run_time=0.6, ease="out-cubic")
    await s.play(line.animate.fade_in(), run_time=0.5)
    await s.play(rule.animate.draw_on(), run_time=0.8)
    await s.play(dot.animate.fade_in(), run_time=0.4)
    await s.play(dot.animate.move_by(1060, 0), run_time=1.4, ease="in-out")
    await s.wait(READ)
    await s.beat()
