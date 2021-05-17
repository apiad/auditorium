"""
`auditorium.show` contains the definition of the `Show` class.
"""

# The `Show` class is the main.

from pathlib import Path

from jinja2 import Template

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
