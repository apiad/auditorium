# This is a demo slideshow to showcase the main features of `auditorium`.
# In auditorium, a slideshow starts with a `Show` class.

from auditorium import Show, Context

# We being by creating an instance of the Show.

show = Show()

# A show is composed of slides. Each slide is a function, decorated with
# a special decorator.

@show.slide
def intro(ctx: Context):
    ctx.text("Hello world! 🖖")

# Finally, we call `show.run()`

show.run()
