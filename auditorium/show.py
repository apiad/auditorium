"""
`auditorium.show` contains the definition of the `Show` class.
"""

# The `Show` class is the main.

from pathlib import Path
from typing import Dict, List, Optional

from dataclasses import dataclass, asdict
from jinja2 import Template

import asyncio
import abc
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2.nodes import And

from pydantic import BaseModel


class Show:
    def __init__(self) -> None:
        self.app = FastAPI()
        self.app.mount("/assets", StaticFiles(directory=Path(__file__).parent / "assets"))
        self.app.get("/")(self._index)
        self.app.websocket("/ws")(self._ws)
        self.slides: Dict[str, Slide] = {}

    async def _index(self):
        template = Template((Path(__file__).parent / "templates" / "slide.jinja").read_text())
        return HTMLResponse(template.render(slides=self.slides))

    async def _ws(self, websocket: WebSocket):
        await websocket.accept()
        data = await websocket.receive_json()
        request = SlideRequest(**data)
        slide = self.slides[request.slide]
        await slide.build(websocket)

    def slide(self, fn):
        slide = Slide(fn)
        self.slides[slide.id] = slide
        return fn

    def run(self, host:str="127.0.0.1", port:int=8000):
        from uvicorn import run
        run(self.app, host=host, port=port)


class SlideRequest(BaseModel):
    slide: str


@dataclass
class BuildCommand:
    content: "HtmlNode"
    type:str = "build"


@dataclass
class UpdateCommand:
    content: "HtmlNode"
    type:str = "update"


class Slide:
    def __init__(self, fn, id=None) -> None:
        self.id = id or fn.__name__
        self.fn = fn

    async def build(self, websocket: WebSocket):
        context = Context(self.id, websocket)
        await self.fn(context)


class Context:
    def __init__(self, slide_id:str, websocket: WebSocket) -> None:
        self._slide_id = slide_id
        self._auto_counter = 0
        self._websocket = websocket

    def __autokey(self):
        self._auto_counter += 1
        return str(self._auto_counter)

    async def sleep(self, delay:float):
        await asyncio.sleep(delay)

    async def text(self, text:str, key:str=None) -> "Text":
        text = Text(text, key=self._slide_id + ":" + (key or self.__autokey()), websocket=self._websocket)
        await text.create()
        return text


class Component(abc.ABC):
    def __init__(self, key, websocket: WebSocket) -> None:
        self.key = key
        self._websocket = websocket

    async def create(self):
        await self._websocket.send_json(asdict(BuildCommand(content=self._build())))

    async def update(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self, k, v)

        await self._websocket.send_json(asdict(UpdateCommand(content=self._build())))

    @abc.abstractmethod
    def _build(self) -> str:
        pass


@dataclass
class HtmlNode:
    tag: str
    id: str
    text: Optional[str] = None
    children: List["HtmlNode"] = tuple()


class Text(Component):
    def __init__(self, text, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.text = text

    def _build(self) -> str:
        return HtmlNode(tag="div", id=self.key, text=self.text)
