# This is a demo slideshow to showcase the main features of `auditorium`.
# In auditorium, a slideshow starts with a `Show` class.

import random
from auditorium import Show, Context

# We being by creating an instance of the Show.

show = Show()

# A show is composed of slides. Each slide is a function, decorated with
# a special decorator.


@show.slide
async def intro(ctx: Context):
    _, _, text2, _, text3 = await ctx.create(
        ctx.stretch(),
        ctx.text("Welcome to Auditorium 2.0! 🖖", size=5),
        ctx.text(
            "🔥 A Python framework for composing HTML animations!",
            size=3,
        ).scaled(0),
        ctx.stretch(),
        ctx.text("⬇️ Hit SPACE to continue").animated("bounce").transparent(),
    )

    await ctx.sequential(1, text2.restore(1), 1.5, text3.restore(0.5))


@show.slide
async def quickstart(ctx: Context):
    await ctx.text(
        "Auditorium is Python framework for creating animated HTML+CSS slideshows", size=2
    ).create()

    boxes = await ctx.create(*[ctx.shape(width=32, height=32) for _ in range(10)])

    while await ctx.loop():
        await ctx.sleep(1)
        await ctx.parallel(
            *[
                b.transform(
                    translate_x=random.uniform(-400, 400),
                    translate_y=random.uniform(-200, 200),
                    rotate=random.uniform(-360, 360),
                    duration=1,
                )
                for b in boxes
            ]
            + [
                b.update(
                    color=random.choice("red green blue yellow".split())
                    + "-"
                    + str(random.randint(2, 6) * 100)
                )
                for b in boxes
            ]
        )


# Finally, we call `show.run()`

show.run()
