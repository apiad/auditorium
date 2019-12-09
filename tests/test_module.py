# coding: utf8

from auditorium import Show


def test_show():
    show = Show()

    assert show.current_slide is None


def test_one_slide():
    show = Show()

    @show.slide
    def slide_one():
        "## Title"

    assert show.slide_ids == ['slide_one']
    assert show.slides['slide_one'] == slide_one
