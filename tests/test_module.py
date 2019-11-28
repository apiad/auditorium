# coding: utf8

from auditorium import Show

def test_show():
    show = Show(__name__)

    assert show.current_slide is None
