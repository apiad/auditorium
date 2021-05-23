# This is a demo slideshow to showcase the main features of `auditorium`.
# In auditorium, a slideshow starts with a `Show` class.

from auditorium import Show, Context

# We being by creating an instance of the Show.

show = Show()

# A show is composed of slides. Each slide is a function, decorated with
# a special decorator.

@show.slide
async def intro(ctx: Context):
    text1 = await ctx.text("Hello world! 🖖")
    await ctx.sleep(0.5)
    await ctx.text("Another sentence!")
    await ctx.sleep(0.5)
    await text1.update(text="Here I am!")

# Finally, we call `show.run()`

show.run()
