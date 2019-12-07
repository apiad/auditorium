# coding: utf8

"""
A simple demo script for `auditorium`.
"""

from auditorium import Show

show = Show("Auditorium Demo")


@show.slide
def intro():
    """
    # Auditorium
    ## A Python-powered slideshow generator with steroids
    """


@show.slide
def what_is_this():
    """
    ## What is Auditorium

    `auditorium` is a Python module for creating slideshows which
    are ultimately displayed in a browser using the amazing
    library `reveal.js`.

    With `auditorium` you don't need to learn JavaScript,
    HTML or CSS. Everything goes in your Python code,
    both presentation content and logic.
    """


@show.slide
def how_it_works():
    """
    ## How it works

    `auditorium` creates a continuous feedback loop between Python
    and HTML/JavaScript.

    * Every slide in `auditorium` is a Python method.
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
    from auditorium import Show
    show = Show("Auditorium Demo")""")

    show.markdown("add a method for every slide, decorated with `@show.slide`.")

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
def layout():
    """
    ## Custom layout

    More complex layouts can be compossed.
    """

    show.hrule()

    with show.columns(2, 3) as cl:
        show.markdown("#### Content")
        show.markdown("You can put custom content in any column...")

        cl.tab()
        show.code("""
        with show.columns(2, 3) as cl:
            show.markdown("#### Content")
            show.markdown("...")

            cl.tab()
            show.code("...")
        """)


@show.slide
def data_binding():
    """
    ## Dynamic Data

    Use dynamic data with two-way binding to add executable Python logic
    to your presentation.
    """

    with show.columns(2) as cl:
        text = show.text_input("dlrow")
        text = "".join(reversed(text)).title()
        cl.tab()
        show.markdown(f"Hello {text}!!")

    show.hrule()

    show.code("""
    @show.slide
    def data_binding():
        # ...
        text = show.text_input("dlrow")
        text = "".join(reversed(text)).title()
        show.markdown(f"Hello {text}!!")
    """)


@show.slide
def animation():
    """
    ## Animations

    You can create simple stateless animations with pure Python
    """

    with show.animation(steps=10, time=0.33, loop=True) as anim:
        show.markdown("> ### ." + ("." * anim.current))

    show.hrule()

    show.code("""
    with show.animation(steps=10, time=0.33, loop=True) as anim:
        show.markdown("> ### ." + ("." * anim.current))
    """)


@show.slide
def blocks():
    """
    ## Blocks

    Like beamer, pre-styled blocks are available.
    """
    with show.columns(2) as cl:

        with show.block('Standard block'):
            show.markdown("And its content...")

        with show.success('Success block'):
            show.markdown("For happy endings...")

        cl.tab()

        with show.warning('Warning block'):
            show.markdown("For hairy stuff...")

        with show.error('Error block'):
            show.markdown("When nothing works...")


with show.vertical():
    @show.slide
    def vertical_1():
        """
        ## Vertical Slides

        Vertical slides allow you to create "read-more" like
        features in your slideshow.
        They can be skipped on shorter presentations and left
        for more interested audiences.
        """

        with show.warning():
            show.markdown('Press `DOWN` instead of `LEFT` or click the down arrow.')

    @show.slide
    def vertical_2():
        """
        ## Vertical Slides: Code
        """

        show.code("""
        with show.vertical():

            @show.slide
            def vertical_1():
                # content of first vertical slide

            @show.slide
            def vertical_2():
                # content of second vertical slide
        """)


with show.vertical():

    @show.slide
    def fragments():
        """
        ## Fragments

        Fragments allow to animate elements inside a slide.
        """

        with show.fragment():
            show.markdown("The can have different animations as well...")

        with show.fragment():
            show.hrule()
            show.code("""
            with show.fragment(style='...'): # fade-in, grow, ...
                # content
            """)

    @show.slide
    def fragment_examples():
        """
        ## Fragment examples

        Here are some of the possible fragment animations.
        """

        with show.columns(3) as cl:
            for i, style in enumerate('grow shrink fade-in fade-out fade-up fade-down fade-left fade-right highlight-blue highlight-red highlight-green'.split()):
                if i > 0 and i % 4 == 0:
                    cl.tab()

                with show.fragment(style):
                    show.markdown(f'`{style}`')




with show.vertical():
    @show.slide
    def pyplot():
        """
        ## pyplot

        Dynamically generated graphs with `pyplot` can be added
        also very easily.
        """
        from matplotlib import pyplot as plt
        import numpy as np

        xg = np.random.RandomState(0)
        yg = np.random.RandomState(1)

        with show.columns(2) as cl:
            with show.animation(steps=60, time=0.5, loop=True) as anim:
                x = xg.uniform(size=anim.current * 50)
                y = yg.uniform(size=anim.current * 50)
                colors = ['green' if xi ** 2 + yi ** 2 < 1 else 'orange' for (xi, yi) in zip(x,y)]
                plt.scatter(x, y, s=3, c=colors)
                plt.ylim(0, 1)
                plt.xlim(0, 1)
                show.pyplot(plt, fmt='png', height=350)

                cl.tab()

                with show.block('Monte Carlo Sampling'):
                    show.markdown(f"Samples: {len(x)}")
                    show.markdown(f"Inside: {colors.count('green')}")
                    show.markdown("**Pi = %.3f**" % (4 * colors.count('green') / len(x) if len(x) > 0 else 0))

    @show.slide
    def pyplot_code():
        """### Pyplot: Code"""

        show.code("""
        xg = np.random.RandomState(0)
        yg = np.random.RandomState(1)

        with show.animation(steps=60, time=0.5, loop=True) as anim:
            x = xg.uniform(size=anim.current * 50)
            y = yg.uniform(size=anim.current * 50)
            colors = ['green' if xi ** 2 + yi ** 2 < 1 else 'orange'
                       for (xi, yi) in zip(x,y)]
            plt.scatter(x, y, s=3, c=colors)
            plt.ylim(0, 1)
            plt.xlim(0, 1)
            show.pyplot(plt, fmt='png', height=350)
        """)


if __name__ == "__main__":
    show.run("localhost", 5050, debug=True)
