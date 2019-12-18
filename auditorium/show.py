# coding: utf8

"""
This module includes the `Show` class and the main functionalities of `auditorium`.
"""

import base64
import io
import runpy
import webbrowser
from collections import OrderedDict

from jinja2 import Template
from markdown import markdown
from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from sanic import Sanic
from sanic.response import html, json

from .components import Animation, Block, Column, Fragment, ShowMode
from .utils import fix_indent, path


class Show:
    def __init__(self, title="", theme="white", code_style="monokai"):
        self.theme = theme
        self.formatter = HtmlFormatter(style=get_style_by_name(code_style))

        self._slides = {}
        self._sections = []

        self.app = Sanic("auditorium")
        self.app.route("/")(self._index)
        self.app.route("/update", methods=["POST"])(self._update)
        self.app.static("static", path("static"))

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

    def run(self, host, port, launch, *args, **kwargs):
        self._content = self._render_content()

        if launch:

            def launch_server():
                webbrowser.open_new_tab(f"http://{host}:{port}")

            self.app.add_task(launch_server)

        self.app.run(host=host, port=port, *args, **kwargs)

    @property
    def show_title(self):
        return self._title

    def append(self, show, instance_name="show"):
        if isinstance(show, str):
            show = Show.load(show, instance_name)

        self._tail.append(show)

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

    @property
    def slides(self):
        return self._slides

    @property
    def sections(self):
        return self._sections

    ## @slide decorator

    def slide(self, func=None, id=None):
        if func is not None:
            return self._wrap(func, id)

        elif id is not None:

            def wrapper(func):
                return self._wrap(func, id)

            return wrapper

    def _wrap(self, func, id):
        if self._rendering:
            return func

        slide_id = id or func.__name__
        slide = Slide(slide_id, func, self)
        self._slides[slide_id] = slide

        if self._current_section is None:
            # We are at the top level, this a regular slide
            section = Section()
            section.add_slide(slide)

            self._sections.append(section)
            self._current_section = section

            # recursively build this slide (just once)
            # to reach the vertical slides
            slide.run(ShowMode.Markup)

            self._current_section = None
        else:
            # We are inside a slide, this a vertical slide
            section = self._current_section
            section.add_slide(slide)

        return func

    ## Internal API

    def do_markup(self, slide):
        slide = self._slides[slide]
        ctx = slide.run(ShowMode.Markup)
        return "\n\n".join(ctx.content)

    def do_code(self, slide, values):
        slide = self._slides[slide]
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

    async def _update(self, request):
        data = request.json
        values = {}
        values[data["id"]] = data["value"]
        update = self.do_code(data["slide"], values)
        return json(update)

    async def _index(self, request):
        theme = request.args.get("theme", self.theme)
        return html(
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
