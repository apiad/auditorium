# coding: utf8

from reveal import Show

show = Show(__name__)


@show.slide
def slide0():
    """
    ## First slide

    This is the first slide...
    """


@show.slide
def slide1():
    """
    ## Hello World

    This is the second slide
    """


if __name__ == "__main__":
    show.run("localhost", 5050, debug=True)
