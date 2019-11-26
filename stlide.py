import streamlit as st


current_slide = 0
slides = []
slides_by_id = {}


def render():
    global current_slide
    current_slide = st.sidebar.slider('Slide', 1, len(slides)) - 1
    slides[current_slide]()


def initialize():
    slides.clear()


def slide(func):
    slides.append(func)
    slides_by_id[func.__name__] = func
    return func


# def slide(idx):
#     return StreamlitWrapper(st, idx)


class StreamlitWrapper:
    def __init__(self, st, idx):
        self.st = st
        self.idx = idx

    def __getattr__(self, attr):
        if current_slide == self.idx:
            return getattr(self.st, attr)

        return Null

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class NullObject:
    def __getattr__(self, attr):
        return self

    def __call__(self, *args, **kwargs):
        return self

    def __bool__(self):
        return False


Null = NullObject()
