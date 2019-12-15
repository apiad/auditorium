# coding: utf8

from auditorium import Show


def test_one_slide():
    show = Show()

    @show.slide
    def slide_one(ctx):
        "## Title"

    assert 'slide_one' in show.slides
    assert len(show.sections) == 1


def test_vertical_slide():
    show = Show()

    @show.slide
    def main(ctx):

        @show.slide
        def second(ctx):
            pass

    show.render()

    assert len(show.slides) == 2
    assert len(show.sections) == 1


def test_demo():
    "Make sure the demo runs without exceptions at least one"

    from auditorium.demo import show
    show.render()


def test_md_demo():
    "Make sure the Markdown-first demo runs without exceptions as well"

    from auditorium.markdown import MarkdownLoader
    show = MarkdownLoader("auditorium/static/md/demo.md").parse()
    show.render()
