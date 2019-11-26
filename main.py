# coding: utf8

from reveal import Show

show = Show(__name__)


@show.slide
def slide0():
    """
    # First slide
    """


@show.slide
def slide1():
    """
    # Hello World
    """


if __name__ == "__main__":
    show.run("localhost", 5050, debug=True)
