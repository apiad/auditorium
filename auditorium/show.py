# coding: utf8

"""
This module includes the `Show` class and the main functionalities of `auditorium`.
"""

import base64
import io
import runpy
import warnings
import webbrowser
from collections import OrderedDict

from jinja2 import Template
from markdown import markdown
from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from starlette.responses import HTMLResponse
from pydantic import BaseModel
from typing import Union

from .components import Animation, Block, Column, Fragment, ShowMode
from .utils import fix_indent, path


class UpdateData(BaseModel):
    type: str
    id: str
    slide: str
    value: Union[int, str]


class Show(FastAPI):
    def __init__(self, title="", theme="white", code_style="monokai"):
        self.theme = theme
        self.formatter = HtmlFormatter(style=get_style_by_name(code_style))

        self._slides = {}
        self._sections = []
        self._tail = []

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

    def run(self, host: str, port: int, launch: bool, *args, **kwargs) -> None:
        self._content = self._render_content()

        # if launch:
        #     def launch_server():
        #         webbrowser.open_new_tab(f"http://{host}:{port}")

        #     self.app.add_task(launch_server)

        try:
            import uvicorn

            uvicorn.run(self.app, host=host, port=port, *args, **kwargs)
        except ImportError:
            warnings.warn("In order to call `run` you need `uvicorn` installed.")
            exit(1)

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
    def __init__(self, slide_id, mode, show, values=None):
        self.content = []
        self.update = {}
        self.slide_id = slide_id
        self.unique_id = 0
        self.mode = mode
        self.values = values
        self.show = show

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
        ctx = Context(self.slide_id, mode, self._show, values)

        if self._func.__doc__:
            ctx.markdown(self._func.__doc__)

        self._func(ctx)
        return ctx
