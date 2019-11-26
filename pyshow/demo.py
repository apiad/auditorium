# coding: utf8

from pyshow import Show

show = Show(__name__)


@show.slide
def intro():
    show.markdown("# pyshow")
    show.markdown("## Python powered slideshows right in your browser")

@show.slide
def what_is_this():
    show.markdown("## What is PyShow")
    show.markdown("""
    `pyshow` is a Python module for creating slideshows which
    are ultimately displayed in a browser using the amazing
    library `reveal.js`.
    """)
    show.markdown("""
    With `pyshow` you don't need to learn JavaScript,
    HTML or CSS. Everything goes in your Python code,
    both presentation content and logic.
    """)
    show.anchor(how_it_works, "See how it works...")

@show.slide
def how_it_works():
    show.markdown("## How it works")
    show.markdown("""
    `pyshow` setups a continuous feedback loop between Python
    and HTML/JavaScript that works automagically.
    """)
    show.markdown("""
    * Every slide in `pyshow` is a Python method.
    * You can mix up content with logic.
        - Inject variables into the presentation.
        - Receive back interaction events and values.
    * Layout is handled by `reveal.js`.
    * You only ever need to write Python code.
    """)

@show.slide
def the_basics():
    show.markdown("## The basics")
    show.markdown("Start by declaring a `Show` instance.")
    show.code("""
    from pyshow import Show
    show = Show(__name__)""")
    show.markdown("The add a method for every slide, decorated with `@show.slide`.")
    show.code("""
    @show.slide
    def my_slide():
        # slide content
    """)
    show.markdown("Finally run the show.")
    show.code("show.run('localhost', 5050)")

@show.slide
def static_content():
    show.markdown("## Some examples")
    show.markdown("Static content is added with markdown.")
    show.markdown("You can use **markdown** _formatting_.")

    show.markdown("<hr>")

    show.code("""
    @show.slide
    def static_content():
        show.markdown("## Some examples")
        show.markdown("Static content is added with markdown.")
        show.markdown("You can use **markdown** _formatting_.")
    """)

@show.slide
def data_binding():
    show.markdown("## Some examples")
    show.markdown("""
    Use dynamic data with two-way binding to add complex Python logic
    to your presentation. Try changing the text in the following input.""")

    text = show.text_input("dlrow")
    text = "".join(reversed(text)).title()
    show.markdown(f"> Hello {text}!!")

    show.markdown("<hr>")

    show.code("""
    @show.slide
    def data_binding():
        # ...
        text = show.text_input("dlrow")
        text = "".join(reversed(text)).title()
        show.markdown(f"> Hello {text}!!")
    """)


if __name__ == "__main__":
    show.run("localhost", 5050, debug=True)
