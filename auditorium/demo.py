# coding: utf8

"""
A simple demo script for `auditorium`.
"""

from auditorium import Show

show = Show(__name__)


@show.slide
def intro():
    """
    # pyshow
    ## Python powered slideshows right in your browser
    """

@show.slide
def what_is_this():
    """
    ## What is PyShow

    `pyshow` is a Python module for creating slideshows which
    are ultimately displayed in a browser using the amazing
    library `reveal.js`.

    With `pyshow` you don't need to learn JavaScript,
    HTML or CSS. Everything goes in your Python code,
    both presentation content and logic.
    """

    show.anchor(how_it_works, "See how it works...")

@show.slide
def how_it_works():
    """
    ## How it works

    `pyshow` setups a continuous feedback loop between Python
    and HTML/JavaScript that works automagically.

    * Every slide in `pyshow` is a Python method.
    * You can mix up content with logic.
        - Inject variables into the presentation.
        - Receive back interaction events and values.
    * Layout is handled by `reveal.js`.
    * You only ever need to write Python code.
    """

@show.slide
def the_basics():
    show.markdown("## The basics")
    show.markdown("Start by declaring a `Show` instance.")

    show.code("""
    from pyshow import Show
    show = Show(__name__)""")

    show.markdown("Then add a method for every slide, decorated with `@show.slide`.")

    show.code("""
    @show.slide
    def my_slide():
        # slide content
    """)

    show.markdown("Finally run the show.")

    show.code("show.run('localhost', 5050)")

@show.slide
def examples():
    show.header("Some examples")
    show.markdown("Slide content is added with _markdown_.")
    show.markup("Or <strong>directly</strong> as HTML.")

    show.hrule()

    show.code("""
    @show.slide
    def example():
        show.header("Some examples")
        show.markdown("Slide content is added with _markdown_.")
        show.markup("Or <strong>directly</strong> as HTML.")
    """)

@show.slide
def static_content():
    """
    ## Static Content

    Static content can also be added directly as markdown in
    the `docstring` of the corresponding method.
    """

    show.hrule()

    show.code("""
    @show.slide
    def static_content():
        \"\"\"
        ## Static Content

        Static content can also be added directly as markdown in
        the `docstring` of the corresponding method.
        \"\"\"
    """)

@show.slide
def data_binding():
    """
    ## Dynamic Data

    Use dynamic data with two-way binding to add complex Python logic
    to your presentation.
    """

    text = show.text_input("dlrow")
    text = "".join(reversed(text)).title()
    show.markdown(f"> Hello {text}!!")

    show.hrule()

    show.code("""
    @show.slide
    def data_binding():
        # ...
        text = show.text_input("dlrow")
        text = "".join(reversed(text)).title()
        show.markdown(f"> Hello {text}!!")
    """)

@show.slide
def pyplot():
    """
    ## pyplot

    Dynamically generated graphs with `pyplot` can be added
    also very easily.
    """
    from matplotlib import pyplot as plt
    import numpy as np

    function = show.text_input("sin(x) * cos(2 * x)")
    x = np.linspace(0, 10, 100)
    y = eval(function, np.__dict__, dict(x=x))
    plt.plot(x, y)
    show.pyplot(plt, fmt='png', height=350)


if __name__ == "__main__":
    show.run("localhost", 5050, debug=True)
