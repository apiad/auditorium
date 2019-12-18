# coding: utf8

"""
A simple demo script for `auditorium`.
"""

from auditorium import Show

show = Show("Auditorium Demo")


@show.slide
def intro(ctx):
    """
    # Auditorium
    ## A Python-powered slideshow generator with steroids
    """


@show.slide
def what_is_this(ctx):
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
def how_it_works(ctx):
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
def the_basics(ctx):
    ctx.markdown("## The basics")
    ctx.markdown("Start by declaring a `Show` instance.")

    ctx.code(
        """
        from auditorium import Show
        show = Show("Auditorium Demo")
        """
    )

    ctx.markdown("Add a method for every slide, decorated with `@show.slide`.")

    ctx.code(
        """
        @show.slide
        def my_slide(ctx):
            # slide content
        """
    )

    ctx.markdown("Finally run the show.")

    ctx.code("auditorium run [file.py]", "bash")


@show.slide
def examples(ctx):
    ctx.header("Some examples")
    ctx.markdown("Slide content is added with _markdown_.")
    ctx.markup("Or <strong>directly</strong> as HTML.")

    ctx.hrule()

    ctx.code(
        """
        @show.slide
        def example(ctx):
            ctx.header("Some examples")
            ctx.markdown("Slide content is added with _markdown_.")
            ctx.markup("Or <strong>directly</strong> as HTML.")
        """
    )


@show.slide
def static_content(ctx):
    """
    ## Static Content

    Static content can also be added directly as markdown in
    the `docstring` of the corresponding method.
    """

    ctx.hrule()

    ctx.code(
        """
        @show.slide
        def static_content(ctx):
            \"\"\"
            ## Static Content

            Static content can also be added directly as markdown in
            the `docstring` of the corresponding method.
            \"\"\"
        """
    )


@show.slide
def layout(ctx):
    """
    ## Custom layout

    More complex layouts can be composed.
    """

    ctx.hrule()

    with ctx.columns(2, 3) as cl:
        ctx.markdown("#### Content")
        ctx.markdown("You can put custom content in any column...")

        cl.tab()
        ctx.code(
            """
            with ctx.columns(2, 3) as cl:
                ctx.markdown("#### Content")
                ctx.markdown("...")

                cl.tab()
                ctx.code("...")
            """
        )


@show.slide
def data_binding(ctx):
    """
    ## Dynamic Data

    Use dynamic data with two-way binding to add executable Python logic
    to your presentation.
    """

    with ctx.columns(2) as cl:
        text = ctx.text_input("dlrow")
        text = "".join(reversed(text)).title()
        cl.tab()
        ctx.markdown(f"Hello {text}!!")

    ctx.hrule()

    ctx.code(
        """
        @show.slide
        def data_binding(ctx):
            # ...
            text = ctx.text_input("dlrow")
            text = "".join(reversed(text)).title()
            ctx.markdown(f"Hello {text}!!")
        """
    )


@show.slide
def animation(ctx):
    """
    ## Animations

    You can create simple stateless animations with pure Python
    """

    with ctx.animation(steps=10, time=0.33, loop=True) as anim:
        ctx.markdown("> ### ." + ("." * anim.current))

    ctx.hrule()

    ctx.code(
        """
        with ctx.animation(steps=10, time=0.33, loop=True) as anim:
            ctx.markdown("> ### ." + ("." * anim.current))
        """
    )


@show.slide
def vertical_slides(ctx):
    """
    ## Vertical Slides

    Vertical slides allow you to create "read-more" like
    features in your slideshow.
    They can be skipped on shorter presentations and left
    for more interested audiences.
    """

    with ctx.warning(ctx):
        ctx.markdown("Press `DOWN` instead of `LEFT` or click the down arrow.")

    @show.slide
    def vertical_code(ctx):
        """
        ## Vertical Slides: Code
        """

        ctx.code(
            """
            @show.slide
            def main_slide(ctx):
                # content of main slide

                @show.slide
                def vertical_1(ctx):
                    # content of first vertical slide

                @show.slide
                def vertical_2(ctx):
                    # content of first vertical slide
            """
        )

    @show.slide
    def vertical_more(ctx):
        """
        ### Vertical Slides: More Info

        If you press `SPACE` instead of `LEFT` or `DOWN`
        the slideshow will cycle through **all** of the slides
        in order, including vertical slides.

        Show will go down and left automatically as necessary.
        """


@show.slide
def blocks(ctx):
    """
    ## Blocks

    Like beamer, pre-styled blocks are available.
    """

    with ctx.columns(2) as cl:

        with ctx.block("Standard block"):
            ctx.markdown("And its content...")

        with ctx.success("Success block"):
            ctx.markdown("For happy endings...")

        cl.tab()

        with ctx.warning("Warning block"):
            ctx.markdown("For hairy stuff...")

        with ctx.error("Error block"):
            ctx.markdown("When nothing works...")

    @show.slide
    def blocks_code(ctx):
        """
        ## Blocks: Code
        """

        ctx.code(
            """
            with ctx.block('Standard block'):
                ctx.markdown("And its content...")

            with ctx.success('Success block'):
                ctx.markdown("For happy endings...")

            with ctx.warning('Warning block'):
                ctx.markdown("For hairy stuff...")

            with ctx.error('Error block'):
                ctx.markdown("When nothing works...")
            """
        )


@show.slide
def fragments(ctx):
    """
    ## Fragments

    Fragments allow to animate elements inside a slide.
    """

    with ctx.fragment(ctx):
        ctx.markdown("The can have different animations as well...")

    with ctx.fragment(ctx):
        ctx.hrule()
        ctx.code(
            """
            with ctx.fragment(style='...'): # fade-in, grow, ...
                # content
            """
        )

    @show.slide
    def fragment_examples(ctx):
        """
        ## Fragment examples

        Here are some of the possible fragment animations.
        """

        with ctx.columns(3) as cl:
            for i, style in enumerate(
                "grow shrink fade-in fade-out fade-up fade-down fade-left \
                 fade-right highlight-blue highlight-red highlight-green".split()
            ):
                if i > 0 and i % 4 == 0:
                    cl.tab()

                with ctx.fragment(style):
                    ctx.markdown(f"`{style}`")


@show.slide
def pyplot(ctx):
    """
    ## pyplot

    Dynamically generated graphs with `pyplot` can be added
    also very easily.
    """
    from matplotlib import pyplot as plt
    import numpy as np

    xg = np.random.RandomState(0)
    yg = np.random.RandomState(1)

    with ctx.columns(2) as cl:
        with ctx.animation(steps=60, time=0.5, loop=True) as anim:
            x = xg.uniform(size=anim.current * 50)
            y = yg.uniform(size=anim.current * 50)
            colors = [
                "green" if xi ** 2 + yi ** 2 < 1 else "orange" for (xi, yi) in zip(x, y)
            ]
            plt.scatter(x, y, s=3, c=colors)
            plt.ylim(0, 1)
            plt.xlim(0, 1)
            ctx.pyplot(plt, fmt="png", height=350)

            cl.tab()

            with ctx.block("Monte Carlo Sampling"):
                ctx.markdown(f"Samples: {len(x)}")
                ctx.markdown(f"Inside: {colors.count('green')}")
                ctx.markdown(
                    "**Pi = %.3f**"
                    % (4 * colors.count("green") / len(x) if len(x) > 0 else 0)
                )

    @show.slide
    def pyplot_code(ctx):
        """### Pyplot: Code"""

        ctx.code(
            """
            xg = np.random.RandomState(0)
            yg = np.random.RandomState(1)

            with ctx.animation(steps=60, time=0.5, loop=True) as anim:
                x = xg.uniform(size=anim.current * 50)
                y = yg.uniform(size=anim.current * 50)
                colors = ['green' if xi ** 2 + yi ** 2 < 1 else 'orange'
                        for (xi, yi) in zip(x,y)]
                plt.scatter(x, y, s=3, c=colors)
                plt.ylim(0, 1)
                plt.xlim(0, 1)
                ctx.pyplot(plt, fmt='png', height=350)
            """
        )


@show.slide
def static_html(ctx):
    """
    ## Going full static

    If you only need `auditorium` for the initial rendering of the HTML,
    and have no animations or interactive code, you can use:
    """

    ctx.code("auditorium render [file] > [output.html]", "bash")

    ctx.markdown(
        """
        This will render the slideshow into a static HTML with all CSS and
        JavaScript embedded, that you can take away and reproduce in any browser,
        or host on a static file server (like Github pages).
        """
    )


@show.slide
def themes(ctx):
    """
    ## Themes
    """

    ctx.markdown("A standard `reveal.js` theme can be specified at creation time:")
    ctx.code("show = Show(theme='black')")

    ctx.markdown("Or directly as a query string arg:")

    with ctx.block(ctx):
        ctx.anchor("/?theme=black#/themes")
