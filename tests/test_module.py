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


def test_demo():
    "Make sure the demo runs without exceptions at least one"

    from auditorium.demo import show
    show.render()


def test_md_demo():
    "Make sure the Markdown-first demo runs without exceptions as well"

    from auditorium.markdown import MarkdownLoader
    show = MarkdownLoader("auditorium/static/md/demo.md").parse()
    show.render()
