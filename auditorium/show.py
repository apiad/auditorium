"""
`auditorium.show` contains the definition of the `Show` class.
"""

# The `Show` class is the main.

from asyncio.tasks import sleep
from pathlib import Path
from typing import Any, AnyStr, Coroutine, Dict, List, Optional

from dataclasses import dataclass, asdict
from fastapi import responses
from jinja2 import Template

import asyncio
import abc
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2.nodes import And

from pydantic import BaseModel
from pydantic.errors import AnyStrMaxLengthError


class Show:
    def __init__(self, *, default_classes="m-2") -> None:
        self.__default_classes = default_classes

        # The center of the `Show` class is a `FastAPI` application
        # that serves the static files, the HTML templates, and the
        # websocket endpoint that communicates the frontend with a `Show` instance.
        self.app = FastAPI()
        self.app.mount(
            "/assets", StaticFiles(directory=Path(__file__).parent / "assets")
        )
        self.app.get("/")(self._index)
        self.app.websocket("/ws")(self._ws)

        # This dictionary maps from a slide's id to its instance.
        self.slides: Dict[str, Slide] = {}

        # These two dictionaries will hold direct and reverse mappings
        # between a slide's id and its index.
        # We will use them for implementing the next/previous functionality.
        self._slide_to_index: Dict[str, int] = {}
        self._index_to_slide: Dict[int, str] = {}

    async def _index(self):
        template = Template(
            (Path(__file__).parent / "templates" / "slide.html").read_text()
        )
        return HTMLResponse(template.render(slides=self.slides))

    async def _ws(self, websocket: WebSocket):
        await websocket.accept()

        request = None

        while True:
            if request is None:
                data = await websocket.receive_json()
                request = SlideRequest(**data)

            print(f"Serving {request}")

            if request.event == "start":
                slide = self.slides[request.slide]
                await slide.build(websocket)

                # We wait until someone unblocks us by pressing a key or something
                request = await self._block(websocket)
                continue

            elif request.event == "keypress":
                # Handle a keypress
                # NOTE: For now we're only implementing moving forward and backward!
                slide_id = request.slide
                slide_idx = self._slide_to_index[slide_id]
                next_idx = slide_idx + 1 if request.keycode == 32 else slide_idx - 1

                # We've done with this request, we have to wait for another
                request = None

                if next_idx not in self._index_to_slide:
                    request = await self._block(websocket)
                    continue

                next_slide = self._index_to_slide[next_idx]
                await websocket.send_json(asdict(GoToCommand(next_slide, 500)))

    async def _block(self, websocket: WebSocket, sleep:float=1) -> "SlideRequest":
        while True:
            await websocket.send_json(asdict(KeypressCommand()))
            data = await websocket.receive_json()
            response = SlideRequest(**data)

            if response.event != "keypress" or response.keycode is not None:
                return response

            await asyncio.sleep(sleep)


    def slide(self, fn):
        slide = Slide(fn, self.__default_classes)
        self._slide_to_index[slide.id] = len(self.slides)
        self._index_to_slide[len(self.slides)] = slide.id
        self.slides[slide.id] = slide
        return fn

    def run(self, host: str = "127.0.0.1", port: int = 8000):
        from uvicorn import run

        run(self.app, host=host, port=port)


class SlideRequest(BaseModel):
    slide: str
    event: str
    keycode: Optional[int] = None


@dataclass
class CreateCommand:
    content: List["HtmlNode"]
    type: str = "create"


@dataclass
class UpdateCommand:
    content: "HtmlNode"
    type: str = "update"


@dataclass
class GoToCommand:
    slide: str
    time: int
    type: str = "goto"


@dataclass
class KeypressCommand:
    type: str = "keypress"


class Slide:
    def __init__(self, fn, default_classes, id=None, margin:int=20) -> None:
        self.id = id or fn.__name__
        self.fn = fn
        self.margin = margin
        self.default_classes = default_classes

    async def build(self, websocket: WebSocket) -> "Context":
        context = Context(self.id, websocket, self.default_classes)
        await self.fn(context)
        return context


class Context:
    def __init__(self, slide_id: str, websocket: WebSocket, default_classes) -> None:
        self.__slide_id = slide_id
        self.__auto_counter = 0
        self.__websocket = websocket
        self.__default_classes = default_classes

    def __autokey(self):
        self.__auto_counter += 1
        return self.__slide_id + ":" + str(self.__auto_counter)

    async def sleep(self, delay: float):
        await asyncio.sleep(delay)

    def text(self, text: str, size: int = 1, **kwargs) -> "Text":
        return Text(
            text,
            size=size,
            key=self.__autokey(),
            websocket=self.__websocket,
            default_classes=self.__default_classes,
            **kwargs,
        )

    def shape(self, **kwargs) -> "Shape":
        return Shape(
            key=self.__autokey(),
            websocket=self.__websocket,
            default_classes=self.__default_classes,
            **kwargs,
        )

    def stretch(self) -> "Stretch":
        return Stretch(
            key=self.__autokey(),
            websocket=self.__websocket,
            default_classes=self.__default_classes,
        )

    async def create(self, *components: "Component"):
        await self.__websocket.send_json(
            asdict(CreateCommand(content=[c._build_content() for c in components]))
        )

        return components

    async def parallel(self, *animations: Coroutine):
        await asyncio.gather(*animations)

    async def sequential(self, *animations: Coroutine):
        animations = [
            asyncio.sleep(a) if isinstance(a, (float, int)) else a for a in animations
        ]

        for a in animations:
            await a

    async def loop(self) -> bool:
        await self.__websocket.send_json(asdict(KeypressCommand()))
        data = await self.__websocket.receive_json()
        response = SlideRequest(**data)

        if response.event == "keypress" and response.keycode is None:
            return True

        return False

    async def keypress(self):
        while await self.loop():
            await self.sleep(1)


class Component(abc.ABC):
    def __init__(
        self,
        key,
        websocket: WebSocket,
        default_classes,
        translate_x=0,
        translate_y=0,
        scale_x=1,
        scale_y=1,
        rotate=0,
        skew_x=0,
        skew_y=0,
        opacity=1,
        transition=None,
    ) -> None:
        self.key = key
        self._websocket = websocket
        self.__default_classes = default_classes.split()
        self._style = {
            "--tw-translate-x": f"{translate_x}px",
            "--tw-translate-y": f"{translate_y}px",
            "--tw-rotate": f"{rotate}deg",
            "--tw-skew-x": f"{skew_x}deg",
            "--tw-skew-y": f"{skew_y}deg",
            "--tw-scale-x": scale_x,
            "--tw-scale-y": scale_y,
            "opacity": f"{opacity}",
            "transform": "translateX(var(--tw-translate-x)) translateY(var(--tw-translate-y)) rotate(var(--tw-rotate)) skewX(var(--tw-skew-x)) skewY(var(--tw-skew-y)) scaleX(var(--tw-scale-x)) scaleY(var(--tw-scale-y))",
            "transition-timing-function": "cubic-bezier(0.4,0,0.2,1)",
        }
        self.__transition_property = "none"
        self.__transition_duration = 0

        if transition is not None:
            self.transition(transition)

    def animated(self, animation:str) -> "Component":
        self.__default_classes.append(f"animate-{animation}")
        return self

    def transparent(self) -> "Component":
        self._style["opacity"] = 0
        return self

    async def animate(self, animation:str):
        await self.animated(animation).update()

    def scaled(self, scale=None, x=None, y=None) -> "Component":
        if scale is not None:
            x = scale
            y = scale

        if x is not None:
            self._style["--tw-scale-x"] = x

        if y is not None:
            self._style["--tw-scale-y"] = y

        return self

    def rotated(self, rotation) -> "Component":
        self._style["--tw-rotate"] = f"{rotation}def"

        return self

    def translated(self, x=None, y=None) -> "Component":
        if x is not None:
            self._style["--tw-translate-x"] = f"{x}px"

        if y is not None:
            self._style["--tw-translate-y"] = f"{y}px"

        return self

    def transition(self, duration: float):
        old_transition = self.__transition_duration

        if duration == 0:
            self.__transition_duration = 0
            self.__transition_property = "none"
        else:
            self.__transition_duration = int(duration * 1000)
            self.__transition_property = "all"

        return old_transition

    def _build_content(self) -> "HtmlNode":
        content = self._build()
        content.clss = " ".join(self.__default_classes) + " " + content.clss
        content.style = dict(self._style, **(content.style or {}))
        content.transition_duration = f"{self.__transition_duration}ms"
        content.transition_property = self.__transition_property
        return content

    async def create(self) -> "Component":
        await self._websocket.send_json(
            asdict(CreateCommand(content=[self._build_content()]))
        )
        return self

    async def update(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

        await self._websocket.send_json(
            asdict(UpdateCommand(content=self._build_content()))
        )

    async def transform(
        self,
        translate_x=None,
        translate_y=None,
        scale_x=None,
        scale_y=None,
        rotate=None,
        skew_x=None,
        skew_y=None,
        opacity=None,
        duration: float = None,
    ):
        old_transition = None

        if duration is not None:
            old_transition = self.transition(duration)

        if translate_x is not None:
            self._style["--tw-translate-x"] = f"{translate_x}px"
        if translate_y is not None:
            self._style["--tw-translate-y"] = f"{translate_y}px"
        if rotate is not None:
            self._style["--tw-rotate"] = f"{rotate}deg"
        if skew_x is not None:
            self._style["--tw-skew-x"] = f"{skew_x}deg"
        if skew_y is not None:
            self._style["--tw-skew-y"] = f"{skew_y}deg"
        if scale_x is not None:
            self._style["--tw-scale-x"] = scale_x
        if scale_y is not None:
            self._style["--tw-scale-y"] = scale_y
        if opacity is not None:
            self._style["opacity"] = opacity

        await self.update()

        if duration is not None:
            await asyncio.sleep(duration)

        if old_transition is not None:
            self.transition(old_transition)

    async def translate(self, x, y, duration: float = None):
        await self.transform(translate_x=x, translate_y=y, duration=duration)

    async def rotate(self, deg, duration: float = None):
        await self.transform(rotate=deg, duration=duration)

    async def scale(self, scale=None, x=None, y=None, duration: float = None):
        if scale is not None:
            x = scale
            y = scale

        await self.transform(scale_x=x, scale_y=y, duration=duration)

    async def restore(self, duration: float = None):
        await self.transform(0, 0, 1, 1, 0, 0, 0, 1, duration)

    @abc.abstractmethod
    def _build(self) -> "HtmlNode":
        pass


@dataclass
class HtmlNode:
    tag: str
    id: str
    transition_duration: int = 0
    transition_property: str = "none"
    clss: List[str] = tuple()
    style: Dict[str, Any] = None
    text: Optional[str] = None
    children: List["HtmlNode"] = tuple()


class Text(Component):
    def __init__(self, text: str, size: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.text = text
        self.size = size

    def _build(self) -> HtmlNode:
        return HtmlNode(
            tag="span", clss=f"text-{self.size}xl", id=self.key, text=self.text
        )


class Stretch(Component):
    def _build(self) -> HtmlNode:
        return HtmlNode(
            tag="div", clss=f"flex-grow", id=self.key
        )


class Shape(Component):
    def __init__(self, width=24, height=24, color="gray-300", **kwargs) -> None:
        super().__init__(**kwargs)
        self._style["width"] = f"{width}px"
        self._style["height"] = f"{height}px"
        self.color = color

    def _build(self) -> "HtmlNode":
        return HtmlNode(
            tag="div", clss=f"bg-{self.color}", id=self.key
        )
