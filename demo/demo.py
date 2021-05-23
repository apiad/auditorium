# This is a demo slideshow to showcase the main features of `auditorium`.
# In auditorium, a slideshow starts with a `Show` class.

from auditorium import Show, Context

# We being by creating an instance of the Show.

show = Show()

# A show is composed of slides. Each slide is a function, decorated with
# a special decorator.


@show.slide
async def intro(ctx: Context):
    _, text2, text3 = await ctx.create(
        ctx.text("Welcome to Auditorium 2.0! 🖖", size="5xl"),
        ctx.text(
            "🔥 A Python framework for composing HTML animations!",
            size="3xl",
            scale_x=0,
            scale_y=0,
        ),
        ctx.text("➡️ Hit LEFT or SPACE to continue", scale_x=0, scale_y=0, translate_y=300),
    )

    await ctx.sequential(1, text2.zoom_in(1), 1.5, text3.zoom_in())


@show.slide
async def quickstart(ctx: Context):
    await ctx.text("Auditorium is Python framework for creating animated HTML+CSS slideshows").create()


# Finally, we call `show.run()`

show.run()
