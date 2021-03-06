"""
`auditorium` is a Python framework for creating slideshows.
"""


# The `Show` class is the main.

from pathlib import Path
from typing import Any, Coroutine, Dict, List, Optional

from dataclasses import dataclass, asdict
from jinja2 import Template

import asyncio
import abc
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect


class Show:
    def __init__(self, *, static_dir: Path = None) -> None:
        # The center of the `Show` class is a `FastAPI` application
        # that serves the static files, the HTML templates, and the
        # websocket endpoint that communicates the frontend with a `Show` instance.
        self.app = FastAPI()
        self.app.mount(
            "/assets", StaticFiles(directory=Path(__file__).parent / "assets")
        )
        self.app.get("/")(self._index)
        self.app.websocket("/ws")(self._ws)

        if static_dir is not None:
            self.app.mount("/static", StaticFiles(directory=static_dir))

        # This dictionary maps from a slide's id to its instance.
        self.slides: Dict[str, Slide] = {}

        # These two dictionaries will hold direct and reverse mappings
        # between a slide's id and its index.
        # We will use them for implementing the next/previous functionality.
        self._slide_to_index: Dict[str, int] = {}
        self._index_to_slide: Dict[int, str] = {}

        self._animations = []
        self._closing = False

    def animation(self, name:str, duration:float=1) -> "Animation":
        animation = Animation(name, duration)
        self.register(animation)
        return animation

    def register(self, animation:"Animation"):
        self._animations.append(animation)

    async def _index(self):
        template = Template(
            (Path(__file__).parent / "templates" / "slide.html").read_text()
        )
        return HTMLResponse(template.render(slides=self.slides, animations=self._animations))

    async def _ws(self, websocket: WebSocket):
        await websocket.accept()

        slide = None
        current_task = None

        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                break

            print(f"Event {data}")

            request = SlideRequest(**data)

            if request.event == "render":
                slide = self.slides[request.slide]
                current_task = asyncio.create_task(slide.build(websocket))
                current_task.add_done_callback(lambda f: f.exception())

            elif request.event == "keypress":
                # Handle a keypress
                slide_id = request.slide

                # if SPACE is pressed we just release the current slide
                # in case it is waiting for a keypress
                if request.keycode == 32:
                    if current_task is not None:
                        slide.context.release()

                # if N or B we go to the next/previous slide respectively
                elif request.keycode in [98, 110]:
                    next_slide = self._next_slide(slide_id) if request.keycode == 110 else self._previous_slide(slide_id)

                    if next_slide is None:
                        continue

                    if current_task is not None:
                        current_task.cancel()
                        current_task = None

                    await websocket.send_json(asdict(GoToCommand(next_slide, 500)))

    def slide(self, fn):
        slide = Slide(fn, self)
        self._slide_to_index[slide.id] = len(self.slides)
        self._index_to_slide[len(self.slides)] = slide.id
        self.slides[slide.id] = slide
        return fn

    def _next_slide(self, slide_id:str):
        slide_index = self._slide_to_index[slide_id] + 1

        if slide_index not in self._index_to_slide:
            return None

        return self._index_to_slide[slide_index]

    def _previous_slide(self, slide_id:str):
        slide_index = self._slide_to_index[slide_id] - 1

        if slide_index not in self._index_to_slide:
            return None

        return self._index_to_slide[slide_index]

    async def run(self, host: str = "127.0.0.1", port: int = 8000):
        from uvicorn import Server, Config

        config = Config(self.app, host=host, port=port)
        self._server = Server(config)

        await self._server.serve()

    async def stop(self):
        self._closing = True
        await self._server.shutdown()


class SlideRequest(BaseModel):
    slide: str
    event: str
    keycode: Optional[int] = None


@dataclass
class CreateCommand:
    content: List["HtmlNode"]
    type: str = "create"


@dataclass
class DestroyCommand:
    content: List[str]
    type: str = "destroy"


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
class MediaCommand:
    id: str
    command: str
    type: str = "media"


class Slide:
    def __init__(self, fn, show:Show, id=None, margin: int = 20) -> None:
        self.id = id or fn.__name__
        self.fn = fn
        self.show = show
        self.margin = margin
        self.enabled = True

    def next_slide(self):
        return self.show._next_slide(self.id)

    async def build(self, websocket: WebSocket) -> "Context":
        self.context = Context(self, websocket)
        await self.fn(self.context)
        return self.context


class Context:
    def __init__(self, slide: Slide, websocket: WebSocket) -> None:
        self._slide = slide
        self.__slide_id = slide.id
        self.__auto_counter = 0
        self.__websocket = websocket
        self._parent: "Component" = None
        self._keypress = asyncio.Event()

    def __autokey(self):
        self.__auto_counter += 1
        return self.__slide_id + "-" + str(self.__auto_counter)

    async def sleep(self, delay: float):
        await asyncio.sleep(delay)

    async def next(self):
        next_slide = self._slide.next_slide()

        if next_slide is not None:
            await self.__websocket.send_json(asdict(GoToCommand(next_slide, 500)))

    def text(self, text: str, size: int = 1, align:str = "left", styling:str="", **kwargs) -> "Text":
        return Text(
            text,
            size=size,
            align=align,
            styling=styling,
            key=self.__autokey(),
            websocket=self.__websocket,
            context=self,
            **kwargs,
        )

    def image(self, src: str, **kwargs) -> "Image":
        return Image(
            src=src,
            key=self.__autokey(),
            websocket=self.__websocket,
            context=self,
            **kwargs,
        )

    def audio(self, src:str, autoplay:bool=False, **kwargs) -> "Audio":
        return Audio(
            src=src,
            autoplay=autoplay,
            key=self.__autokey(),
            websocket=self.__websocket,
            context=self,
            **kwargs,
        )

    def shape(self, **kwargs) -> "Shape":
        return Shape(
            key=self.__autokey(),
            websocket=self.__websocket,
            context=self,
            **kwargs,
        )

    def stretch(self) -> "Stretch":
        return Stretch(
            key=self.__autokey(),
            websocket=self.__websocket,
            context=self,
        )

    def layout(
        self, direction: str, wrap: str, align: str, justify: str, **kwargs
    ) -> "Layout":
        return Layout(
            direction=direction,
            wrap=wrap,
            align=align,
            justify=justify,
            key=self.__autokey(),
            websocket=self.__websocket,
            context=self,
            **kwargs,
        )

    def row(self, **kwargs) -> "Layout":
        return self.layout("row", "wrap", "center", "center", **kwargs)

    def column(self, **kwargs) -> "Layout":
        return self.layout("column", "wrap", "center", "center", **kwargs)

    async def create(self, *components: "Component") -> List["Component"]:
        components = list(self._flatten(components))

        await self.__websocket.send_json(
            asdict(CreateCommand(content=[c._build_content() for c in components]))
        )

        return components

    async def destroy(self, *components: "Component"):
        await self.__websocket.send_json(
            asdict(DestroyCommand(content=[c.key for c in self._flatten(components)]))
        )

    def _flatten(self, seq):
        if hasattr(seq, '__iter__'):
            for x in seq:
                yield from self._flatten(x)
        else:
            yield seq

    def _unwrap(self, seq):
        return [self.sleep(i) if isinstance(i, (float, int)) else i for i in self._flatten(seq)]

    async def parallel(self, *animations: Coroutine):
        await asyncio.gather(*self._unwrap(animations))

    async def sequential(self, *animations: Coroutine):
        for a in self._unwrap(animations):
            await a

    async def keypress(self):
        await self._keypress.wait()

    def release(self):
        self._keypress.set()
        self._keypress.clear()


class Component(abc.ABC):
    def __init__(
        self,
        *,
        key,
        websocket: WebSocket,
        context: Context,
        translate_x=0,
        translate_y=0,
        scale_x=1,
        scale_y=1,
        rotation=0,
        skew_x=0,
        skew_y=0,
        opacity=1,
        transition_duration=0,
        margin=0.5,
        padding=0,
        color: str = "black",
        width: str = "initial",
        height: str = "initial",
        animation: "Animation" = None,
    ) -> None:
        self.key = key
        self.translate_x = translate_x
        self.translate_y = translate_y
        self.scale_x = scale_x
        self.scale_y = scale_y
        self.rotation = rotation
        self.skew_x = skew_x
        self.skew_y = skew_y
        self.opacity = opacity
        self.transition_duration = transition_duration
        self.width = width
        self.height = height
        self.margin = margin
        self.padding = padding
        self.animation = animation
        self.color = color

        self._context = context
        self._websocket = websocket

    def _make_style(self, style):
        pass

    @property
    def style(self):
        style_dict = {
            "opacity": self.opacity,
            "width": self.width,
            "height": self.height,
            "margin": f"{self.margin}rem",
            "padding": f"{self.padding}rem",
            "--translate-x": f"{self.translate_x}px",
            "--translate-y": f"{self.translate_y}px",
            "--rotation": f"{self.rotation}deg",
            "--skew-x": f"{self.skew_x}deg",
            "--skew-y": f"{self.skew_y}deg",
            "--scale-x": f"{self.scale_x}",
            "--scale-y": f"{self.scale_y}",
            "color": self.color,
            "transform": f"translateX(var(--translate-x)) translateY(var(--translate-y)) rotate(var(--rotation)) skewX(var(--skew-x)) skewY(var(--skew-y)) scaleX(var(--scale-x)) scaleY(var(--scale-y))",
            "transition-timing-function": "cubic-bezier(0.4,0,0.2,1)",
            "transition-property": "all",
        }

        if self.animation is not None:
            style_dict["animation-name"] = self.animation._name
            style_dict["animation-duration"] = f"{int(self.animation._duration * 1000)}ms"

        self._make_style(style_dict)
        return style_dict

    def transparent(self) -> "Component":
        self.opacity = 0
        return self

    def scaled(self, scale=None, x=None, y=None) -> "Component":
        if scale is not None:
            x = scale
            y = scale

        if x is not None:
            self.scale_x = x

        if y is not None:
            self.scale_y = y

        return self

    def rotated(self, rotation) -> "Component":
        self.rotation = rotation

        return self

    def translated(self, x=None, y=None) -> "Component":
        if x is not None:
            self.translate_x = x

        if y is not None:
            self.translate_y = y

        return self

    def transition(self, duration: float):
        old_transition = self.transition_duration
        self.transition_duration = duration
        return old_transition

    def _build_content(self) -> "HtmlNode":
        content = self._build()
        content.style = self.style
        content.transition_duration = f"{int(self.transition_duration * 1000)}ms"

        if self._context._parent is not None:
            content.parent = self._context._parent.key

        return content

    async def create(self) -> "Component":
        await self._websocket.send_json(
            asdict(CreateCommand(content=[self._build_content()]))
        )
        return self

    async def update(self, duration: float = None, **kwargs):
        old_transition = None

        if duration is not None:
            old_transition = self.transition(duration)

        for k, v in kwargs.items():
            if v is not None:
                setattr(self, k, v)

        await self._websocket.send_json(
            asdict(UpdateCommand(content=self._build_content()))
        )

        if duration is not None:
            await asyncio.sleep(duration)

        if old_transition is not None:
            self.transition(old_transition)

    async def translate(self, x=0, y=0, duration: float = None):
        await self.update(translate_x=x, translate_y=y, duration=duration)

    async def rotate(self, deg, duration: float = None):
        await self.update(rotate=deg, duration=duration)

    async def scale(self, scale=None, x=1, y=1, duration: float = None):
        if scale is not None:
            x = scale
            y = scale

        await self.update(scale_x=x, scale_y=y, duration=duration)

    async def restore(self, duration: float = None):
        await self.update(
            duration=duration,
            translate_x=0,
            translate_y=0,
            scale_x=1,
            scale_y=1,
            rotation=0,
            skew_x=0,
            skew_y=0,
            opacity=1,
        )

    @abc.abstractmethod
    def _build(self) -> "HtmlNode":
        pass

    def __enter__(self) -> "Component":
        self.__last_parent = self._context._parent
        self._context._parent = self
        return self

    def __exit__(self, *args, **kwargs):
        self._context._parent = self.__last_parent


@dataclass
class HtmlNode:
    tag: str
    id: str
    transition_duration: int = 0
    props: Optional[Dict[str, str]] = None
    clss: str = ""
    style: Dict[str, Any] = None
    text: Optional[str] = None
    children: List["HtmlNode"] = tuple()
    parent: Optional[str] = None


class Text(Component):
    def __init__(self, text: str, size: int, align:str, styling:str="", *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.text = text
        self.size = size
        self.align = align
        self.styling = styling

    def _build(self) -> HtmlNode:
        return HtmlNode(
            tag="div", clss=f"text-{self.size}xl text-{self.align} {self.styling}", id=self.key, text=self.text
        )


class Image(Component):
    def __init__(self, src: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.src = src

    def _build(self) -> HtmlNode:
        return HtmlNode(
            tag="img",
            id=self.key,
            props=dict(src=self.src),
        )


class Audio(Component):
    def __init__(self, src:str, autoplay:bool=False, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.src = src
        self.autoplay=autoplay

    def _build(self) -> HtmlNode:
        return HtmlNode(
            tag="audio",
            id=self.key,
            props=dict(src=self.src),
        )

    async def play(self):
        await self._websocket.send_json(asdict(MediaCommand(id=self.key, command="play")))


class Stretch(Component):
    def _build(self) -> HtmlNode:
        return HtmlNode(tag="div", clss=f"flex-grow", id=self.key)


class Layout(Component):
    def __init__(
        self, direction: str, wrap: str, align: str, justify: str, *children: Component, **kwargs
    ):
        self.direction = direction
        self.wrap = wrap
        self.align = align
        self.justify = justify
        self.children = children
        super().__init__(**kwargs)

    async def create(self) -> "Component":
        with await super().create():
            for element in self.children:
                await element.create()

        return self

    def _make_style(self, style):
        style["display"] = "flex"
        style["flex-direction"] = self.direction
        style["flex-wrap"] = self.wrap
        style["align-items"] = self.align
        style["justify-content"] = self.justify

    def _build(self) -> "HtmlNode":
        return HtmlNode(tag="div", id=self.key)


class Shape(Component):
    def _build(self) -> "HtmlNode":
        return HtmlNode(tag="div", id=self.key)


class Keyframe:
    def __init__(self, percent:float, animation: "Animation"):
        self._percent = percent
        self._animation = animation
        self._rules = {}

    def do(self, **kwargs) -> "Animation":
        for k,v in kwargs.items():
            self._rules[k.replace("_", "-")] = v

        return self._animation

    def __str__(self):
        return f"{self._percent * 100}%"

    def __iter__(self):
        return iter(self._rules.items())


class Animation:
    def __init__(self, name:str, duration: float) -> None:
        self._name = name
        self._duration = duration
        self._keyframes = []

    def at(self, percent) -> Keyframe:
        k = Keyframe(percent, self)
        self._keyframes.append(k)
        return k

    def __str__(self) -> str:
        return self._name

    def __iter__(self):
        return iter(self._keyframes)
