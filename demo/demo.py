# This is a demo slideshow to showcase the main features of `auditorium`.
# In auditorium, a slideshow starts with a `Show` class.
# We also want to import `Context` now, since we'll use it later on for intellisense.

from auditorium import Show, Context

# We beging by creating an instance of the Show.

show = Show()

# A show is composed of slides. Each slide is a function, decorated with
# a special `slide` decorator. Slides are implemented with the `async/await` pattern,
# since under the hood there is a bidirectional connection with the browser
# via websockets.


@show.slide
async def intro(ctx: Context):
    # This is the first slide that will be loaded.
    # Don't worry too much about the content of this method right now, since all of this stuff
    # will be explained in the next slides.

    # Just keep in mind that each slide is an async method that receives a single parameter
    # of type `Context`, which you can use to create and animate HTML objects, as well
    # as to control the state of the slideshow.

    # Everything you do with a `Context` here will be relayed through a websocket to every client
    # that's rendering this slide.
    # For this reason, you'll use a lot of `await` clauses.

    # The next few lines are basically creating a few texts inside a vertically oriented layout,
    # and styled with transparency or scale so that when the slide loads, the HTML elements are
    # created but invisible.

    with await ctx.column(height="100%").create():
        _, text1, text2, _, text3 = await ctx.create(
            ctx.stretch(),
            ctx.text("Welcome to Auditorium 2.0! 🖖", size=5).transparent(),
            ctx.text(
                "🔥 A Python framework for composing HTML animations!",
                size=3,
            ).scaled(0),
            ctx.stretch(),
            ctx.text("⬇️ Hit SPACE to continue").transparent(),
        )

    # And the next line fires up some animations.
    # We'll see this in more detail later on.

    await ctx.sequential(1, text1.restore(2), text2.restore(1), 1.5, text3.restore(0.5))

    # Finally, we wait for a keypress before going to the next slide.

    await ctx.keypress()
    await ctx.next()


# This second slide will show you the most basic building blocks of auditorium.

@show.slide
async def basic(ctx: Context):
    # Each slide in auditorium corresponds to an HTML container inside of which we can
    # create HTML elements and animate them using a mix of JavaScript and CSS.

    # When loaded, each slide is just a plain HTML `div` (with some styles).
    # To fill it with content, we need to create `Component`s.
    pass


@show.slide
async def layouts(ctx: Context):
    await ctx.create(
        ctx.text("The standard layout is fully centered."),
        ctx.text(
            "But you can use the full power of flexbox and grids to compose any layout you desire..."
        ),
    )

    await ctx.stretch().create()

    with await ctx.row().create():
        await ctx.create(
            ctx.text("This text is in a single row"),
            ctx.text("With this other text"),
            ctx.stretch(),
            ctx.text("And this one (after a stretch)"),
        )


# To run the show, we call `auditorium run <path/to/demo.py>` in the terminal.
