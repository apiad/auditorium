"""
`auditorium.show` contains the definition of the `Show` class.
"""

# The `Show` class is the main.

from pathlib import Path

from jinja2 import Template

import abc
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


class Show:
    def __init__(self) -> None:
        self.app = FastAPI()
        self.app.mount("/assets", StaticFiles(directory=Path(__file__).parent / "assets"))
        self.app.get("/")(self._index)
        self.slides = []

    def _index(self):
        template = Template((Path(__file__).parent / "templates" / "slide.jinja").read_text())
        return HTMLResponse(template.render(slides=self.slides))

    def slide(self, fn):
        self.slides.append(Slide(fn))
        return fn

    def run(self, host:str="127.0.0.1", port:int=8000):
        from uvicorn import run
        run(self.app, host=host, port=port)


class Slide:
    def __init__(self, fn, id=None) -> None:
        self.id = id or fn.__name__
        self.fn = fn

    def build(self):
        components = []
        context = Context(self.id, components)
        self.fn(context)
        return components

class Context:
    def __init__(self, slide_id:str, queue:list) -> None:
        self.slide_id = slide_id
        self.auto_counter = 0
        self.queue = queue

    def _autokey(self):
        self.auto_counter += 1
        return str(self.auto_counter)

    def text(self, text:str, key:str=None):
        self.queue.append(Text(text, self.slide_id + ":" + (key or self._autokey())))


class Component(abc.ABC):
    def __init__(self, key) -> None:
        self.key = key

    def build(self) -> str:
        return self._build(self.key)

    @abc.abstractmethod
    def _build(self, key:str) -> str:
        pass


class Text(Component):
    def __init__(self, text, key) -> None:
        super().__init__(key)
        self.text = text

    def _build(self, key: str) -> str:
        return f"<span id={key}>{self.text}</span>"
