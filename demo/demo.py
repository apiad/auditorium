# This is a demo slideshow to showcase the main features of `auditorium`.
# In auditorium, a slideshow starts with a `Show` class.

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
        ctx.text("⬇️ Hit SPACE to continue").scaled(0)
    )

    await ctx.sequential(1, text2.restore(1), 1.5, text3.restore(0.25))
    await text3.animate("bounce")


@show.slide
async def quickstart(ctx: Context):
    await ctx.text(
        "Auditorium is Python framework for creating animated HTML+CSS slideshows"
    ).create()


# Finally, we call `show.run()`

show.run()
