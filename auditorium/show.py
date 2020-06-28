# coding: utf8

"""
This module includes the `Show` class and the main functionalities of `auditorium`.
"""

import asyncio
import base64
import io
import json
import runpy
import warnings
import webbrowser
from collections import OrderedDict
from typing import Union

import websockets
from fastapi import FastAPI
from jinja2 import Template
from markdown import markdown
from pydantic import BaseModel
from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles

from .components import Animation, Block, Column, Fragment, ShowMode
from .utils import fix_indent, path, fix_latex


class UpdateData(BaseModel):
    type: str
    id: str
    slide: str
    value: Union[int, str]


class Show(FastAPI):
    def __init__(self, title="", theme="white", code_style="monokai", metadata=None, context_class=None):
        self.theme = theme
        self.formatter = HtmlFormatter(style=get_style_by_name(code_style))

        self._slides = {}
        self._sections = []
        self._tail = []
        self._metadata = metadata or {}
        self._context_class = context_class or Context

        self.app = FastAPI()
        self.app.get("/")(self._index)
        self.app.post("/update")(self._update)
        self.app.mount("/static", StaticFiles(directory=path("static")))

        self._title = title
        self._current_section = None
        self._rendering = False

        with open(path("templates/content.html")) as fp:
            self._template_content = Template(fp.read())

        with open(path("templates/static.html")) as fp:
            self._template_static = Template(fp.read())

        with open(path("templates/dynamic.html")) as fp:
            self._template_dynamic = Template(fp.read())

    ## Show functions

    def run(self, *, host: str, port: int, debug: bool = False) -> None:
        self._content = self._render_content()

        try:
            import uvicorn

            uvicorn.run(self.app, host=host, port=port, debug=debug)
        except ImportError:
            warnings.warn("(!) You need `uvicorn` installed in order to call `run`.")
            exit(1)

    def publish(self, server: str, name: str):
        url = "{}/ws".format(server)
        asyncio.get_event_loop().run_until_complete(self._ws(url, name))

    async def _ws(self, url: str, name: str):
        try:
            async with websockets.connect(url) as websocket:
                print("Connected to server")
                await websocket.send(name)
                print("Starting command loop.")

                while True:
                    command = await websocket.recv()
                    command = json.loads(command)

                    response = self._do_ws_command(command)
                    response = json.dumps(response)
                    await websocket.send(response)
        except ConnectionRefusedError:
            print("(!) Could not connect to %s. Make sure server is up." % url)
            exit(1)
        except websockets.exceptions.ConnectionClosedError:
            print("(!) Connection to %s closed by server." % url)
            exit(1)


    def _do_ws_command(self, command):
        if command["type"] == "render":
            print("Rendering content")
            return dict(content=self.render())
        if command["type"] == "ping":
            print("Saying hello")
            return dict(msg="pong")
        elif command["type"] == "error":
            print("(!) %s" % command['msg'])
            raise websockets.exceptions.ConnectionClosedError(1006, command['msg'])
        else:
            print("Executing slide %s" % command["slide"])
            values = {}
            values[command["id"]] = command["value"]
            update = self.do_code(command["slide"], values)
            return update

        raise ValueError("Unknown command: %s", command["type"])

    @property
    def show_title(self) -> str:
        return self._title

    def append(self, show, instance_name="show"):
        if isinstance(show, str):
            show = Show.load(show, instance_name)

        self._tail.append(show)
        return self

    @staticmethod
    def load(path, instance_name="show"):
        from .markdown import MarkdownLoader

        if path.endswith(".py"):
            ns = runpy.run_path(path)
            show = ns[instance_name]
        elif path.endswith(".md"):
            loader = MarkdownLoader(path, instance_name=instance_name)
            show = loader.parse()
        else:
            raise ValueError("Invalid path %r" % path)

        return show

    def get_slide(self, slide_id):
        if slide_id in self._slides:
            return self._slides[slide_id]

        for show in self._tail:
            try:
                return show.get_slide(slide_id)
            except:
                pass

        raise ValueError(f"Invalid slide id: {slide_id}")

    @property
    def slides(self):
        yield from self._slides

        for show in self._tail:
            yield from show.slides

    @property
    def sections(self):
        yield from self._sections

        for show in self._tail:
            yield from show.sections

    ## @slide decorator

    def slide(self, func=None, id=None):
        if func is not None:
            return self._wrap(func, id)

        elif id is not None:

            def wrapper(func):
                return self._wrap(func, id)

            return wrapper

    @staticmethod
    def _vertical_slide_wrapper(show, section):
        class _VerticalWrapper:
            def __init__(self, section):
                self.section = section

            def slide(self, func=None, id=None):
                if func is not None:
                    return show._wrap(func, id, self.section)

                elif id is not None:

                    def wrapper(func):
                        return show._wrap(func, id, self.section)

                    return wrapper

        return _VerticalWrapper(section)

    def _wrap(self, func, id, section=None):
        if self._rendering:
            return func

        slide_id = id or func.__name__
        slide = Slide(slide_id, func, self)
        self._slides[slide_id] = slide

        if section is None:
            section = Section()
            section.add_slide(slide)
            self._sections.append(section)
            wrapper = Show._vertical_slide_wrapper(self, section)
            func.slide = wrapper.slide
        else:
            section.add_slide(slide)

        return func

    ## Internal API

    def do_markup(self, slide):
        slide = self.get_slide(slide)
        ctx = slide.run(ShowMode.Markup)
        return "\n\n".join(ctx.content)

    def do_code(self, slide, values):
        slide = self.get_slide(slide)
        ctx = slide.run(ShowMode.Code, values)
        return ctx.update

    def render(self, theme=None):
        return self._template_static.render(
            show=self,
            content=self._render_content(),
            code_style=self._code_style(),
            embed=self._embed,
            theme=theme or self.theme,
        )

    ## Utilities

    def _render_content(self):
        self._rendering = True
        return self._template_content.render(show=self)

    def _embed(self, src):
        with open(path(src)) as fp:
            return fp.read()

    def _code_style(self):
        return self.formatter.get_style_defs(".highlight")

    ## Routes

    async def _update(self, data: UpdateData):
        values = {}
        values[data.id] = data.value
        update = self.do_code(data.slide, values)
        return update

    async def _index(self, theme: str = "white"):
        return HTMLResponse(
            self._template_dynamic.render(
                show=self,
                content=self._content,
                code_style=self._code_style(),
                theme=theme,
            )
        )


class Context:
    def __init__(self, slide_id, mode, show, values=None, metadata=None):
        self.content = []
        self.update = {}
        self.slide_id = slide_id
        self.unique_id = 0
        self.mode = mode
        self.values = values
        self.show = show
        self.metadata = metadata

    ## Utility methods

    def _get_unique_id(self, markup):
        self.unique_id += 1
        item_id = f"{self.slide_id}-{markup}-{self.unique_id - 1}"
        return item_id, f'id="{item_id}" data-slide="{self.slide_id}"'

    ## Binding methods

    def title(self, text):
        return self.header(text, 1)

    def header(self, text, level=2):
        return self.markdown("#" * level + " " + text)

    def hrule(self):
        return self.markup("<hr>")

    def markup(self, content):
        item_id, id_markup = self._get_unique_id("markup")

        if self.mode == ShowMode.Markup:
            self.content.append(f"<div {id_markup}>{fix_indent(content)}</div>")
        else:
            self.update[item_id] = fix_indent(content)

    def markdown(self, content):
        item_id, id_markup = self._get_unique_id("markdown")

        if self.mode == ShowMode.Markup:
            self.content.append(
                f"<div {id_markup}>{markdown(fix_indent(content))}</div>"
            )
        else:
            self.update[item_id] = markdown(fix_indent(content))

    def text_input(self, default="", track_keys=True):
        item_id, id_markup = self._get_unique_id("text-input")

        event = "onkeyup" if track_keys else "onchange"

        if self.mode == ShowMode.Markup:
            self.content.append(
                f'<input {id_markup} data-event="{event}" type="text" class="text" value="{default}"></input>'
            )
            return default
        else:
            return self.values[item_id]

    def pyplot(self, plt, height=400, aspect=4 / 3, fmt="png"):
        item_id, id_markup = self._get_unique_id("pyplot")
        plt.tight_layout()
        buffer = io.BytesIO()
        plt.savefig(buffer, format=fmt)
        plt.clf()
        buffer.seek(0)

        if fmt == "png":
            code = base64.b64encode(buffer.read(-1)).decode("ascii")
            markup = f'<img width="{aspect * height}px" height="{height}px" class="pyplot" src="data:image/png;base64, {code}"></img>'
        elif fmt == "svg":
            code = buffer.read(-1).decode("ascii")
            markup = code
        else:
            raise ValueError(
                "Invalid value for parameter `fmt`, must be 'png' or 'svg'."
            )

        if self.mode == ShowMode.Markup:
            self.content.append(f"<div {id_markup}>{markup}</div>")
        else:
            self.update[item_id] = markup

    def anchor(self, slide_or_href, text=None):
        item_id, id_markup = self._get_unique_id("anchor")

        if self.mode == ShowMode.Markup:
            if hasattr(slide_or_href, "__name__"):
                slide_or_href = "#/" + slide_or_href.__name__

            if text is None:
                text = slide_or_href

            self.content.append(f'<a {id_markup} href="{slide_or_href}">{text}</a>')
        else:
            self.update[item_id] = text

    def code(self, text, language="python"):
        item_id, id_markup = self._get_unique_id("code")
        content = fix_indent(text)

        lexer = get_lexer_by_name(language)
        code = highlight(content, lexer, self.show.formatter)

        if self.mode == ShowMode.Markup:
            self.content.append(f"<div {id_markup}>{code}</div>")
        else:
            self.update[item_id] = code

    def animation(self, steps=10, time=0.1, loop=True) -> Animation:
        item_id, id_markup = self._get_unique_id("animation")

        if self.mode == ShowMode.Markup:
            self.content.append(
                f'<animation {id_markup} data-steps="{steps}" data-time="{time}" data-loop="{loop}"></animation>'
            )
            return Animation(steps, time, loop, 0)

        return Animation(steps, time, loop, self.values[item_id])

    def columns(self, *widths) -> Column:
        return Column(self, *widths)

    def fragment(self, style="fade-in") -> Fragment:
        return Fragment(self, style)

    def block(self, title="", style="default") -> Block:
        return Block(self, title, style)

    def success(self, title="") -> Block:
        return self.block(title, "success")

    def warning(self, title="") -> Block:
        return self.block(title, "warning")

    def error(self, title="") -> Block:
        return self.block(title, "error")

    def latex(self, text, math_type="display"):
        """
        math_type: str
        only accept "display" or "inline"
        this expres the kind of enviroment used
        """
        assert math_type in ("display","inline")
        content = fix_latex(fix_indent(text))
        delimiters = (r'\[',r'\]') if math_type=='display' else (r'$$$',r'$$$')
        print(content)
        if math_type == "inline":
            return f"{delimiters[0]}{content}{delimiters[1]}"

        item_id, id_markup = self._get_unique_id("latex")

        if self.mode == ShowMode.Markup:
            self.content.append(f"<div {id_markup}>{delimiters[0]}{content}{delimiters[1]}</div>")
        else:
            self.update[item_id] = code


class Section:
    def __init__(self):
        self._slides = []
        self._slide_ids = {}

    def add_slide(self, slide):
        if slide.slide_id in self._slide_ids:
            raise ValueError("Duplicated slide name: %r" % slide.slide_id)

        self._slides.append(slide)
        self._slide_ids[slide.slide_id] = slide

    @property
    def slides(self):
        for slide in self._slides:
            yield slide.slide_id


class Slide:
    def __init__(self, slide_id: str, func, show):
        self._slide_id = slide_id
        self._func = func
        self._show = show

    @property
    def slide_id(self) -> str:
        return self._slide_id

    def run(self, mode, values=None) -> Context:
        ctx = self._show._context_class(self.slide_id, mode, self._show, values, self._show._metadata.get(self.slide_id))

        if self._func.__doc__:
            ctx.markdown(self._func.__doc__)

        self._func(ctx)
        return ctx
