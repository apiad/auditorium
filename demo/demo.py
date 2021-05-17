# This is a demo slideshow to showcase the main features of `auditorium`.
# In auditorium, a slideshow starts with a `Show` class.

from auditorium import Show

# We being by creating an instance of the Show.

show = Show()

# A show is composed of slides. Each slide is a function, decorated with
# a special decorator.

@show.slide
def intro():
    pass

@show.slide
def intro():
    pass

# Finally, we call `show.run()`

show.run()
