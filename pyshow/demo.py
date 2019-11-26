# coding: utf8

from pyshow import Show

show = Show(__name__)


@show.slide
def slide0():
    show.markdown("## Initial slide")
    show.markdown("""
    * item 1
    * item 2
    * item 3
    """)


@show.slide
def slide1():
    show.markdown("## Another slide")
    show.markdown("Other content")


if __name__ == "__main__":
    show.run("localhost", 5050, debug=True)
