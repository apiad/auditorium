# coding: utf8

"""
This module includes the `Show` class and the main functionalities of `auditorium`.
"""

import base64
import io
import os
from enum import Enum

import jinja2
from jinja2 import Template
from markdown import markdown
from sanic import Sanic
from sanic.response import html, json

from .components import *
from .utils import fix_indent


def path(p):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), p)


class Show:
    def __init__(self, title="", theme='white'):
        self.slides = {}
        self.slide_ids = []
        self.theme = theme

        self.app = Sanic("auditorium")
        self.app.route("/")(self._index)
        self.app.route("/update", methods=['POST'])(self._update)
        self.app.static('static', path('static'))

        self._title = title
        self.current_content = []
        self.current_update = {}
        self.current_slide = None
        self._unique_id = 0
        self._global_values = {}
        self._mode = ShowMode.Markup

        with open(path('templates/index.html')) as fp:
            self._template = Template(fp.read())

    ## Show functions

    def run(self, host, port, *args, **kwargs):
        self.app.run(host=host, port=port, *args, **kwargs)

    @property
    def show_title(self):
        return self._title

    ## @slide decorator

    def slide(self, func=None, id=None):
        if func is not None:
            slide_id = id or func.__name__
            self.slide_ids.append(slide_id)
            self.slides[slide_id] = func
            return func

        elif id is not None:
            def wrapper(func):
                slide_id = id or func.__name__
                self.slide_ids.append(slide_id)
                self.slides[slide_id] = func
                return func

            return wrapper

    ## Binding methods

    def title(self, text):
        return self.header(text, 1)

    def header(self, text, level=2):
        return self.markdown("#" * level + " " + text)

    def hrule(self):
        return self.markup("<hr>")

    def markup(self, content):
        item_id, id_markup = self._get_unique_id("markup")

        if self._mode == ShowMode.Markup:
            self.current_content.append(f'<div {id_markup}>{fix_indent(content)}</div>')
        else:
            self.current_update[item_id] = fix_indent(content)

    def markdown(self, content):
        item_id, id_markup = self._get_unique_id("markdown")

        if self._mode == ShowMode.Markup:
            self.current_content.append(f'<div {id_markup}>{markdown(fix_indent(content))}</div>')
        else:
            self.current_update[item_id] = markdown(fix_indent(content))

    def text_input(self, default="", track_keys=True):
        item_id, id_markup = self._get_unique_id("text-input")

        event = "onkeyup" if track_keys else "onchange"

        if self._mode == ShowMode.Markup:
            self.current_content.append(f'<input {id_markup} data-event="{event}" type="text" class="text" value="{default}"></input>')
            self._global_values[item_id] = default
            return default
        else:
            return self._global_values[item_id]

    def pyplot(self, plt, height=400, aspect=4/3, fmt="png"):
        item_id, id_markup = self._get_unique_id("pyplot")
        plt.tight_layout()
        buffer = io.BytesIO()
        plt.savefig(buffer, format=fmt)
        plt.clf()
        buffer.seek(0)

        if fmt == 'png':
            code = base64.b64encode(buffer.read(-1)).decode('ascii')
            markup = f'<img width="{aspect * height}px" height="{height}px" class="pyplot" src="data:image/png;base64, {code}"></img>'
        elif fmt == 'svg':
            code = buffer.read(-1).decode('ascii')
            markup = code
        else:
            raise ValueError("Invalid value for parameter `fmt`, must be 'png' or 'svg'.")

        if self._mode == ShowMode.Markup:
            self.current_content.append(f"<div {id_markup}>{markup}</div>")
        else:
            self.current_update[item_id] = markup

    def anchor(self, slide_or_href, text=None):
        item_id, id_markup = self._get_unique_id("anchor")

        if self._mode == ShowMode.Markup:
            if hasattr(slide_or_href, '__name__'):
                slide_or_href = "#/" + slide_or_href.__name__

            if text is None:
                text = slide_or_href

            self.current_content.append(f'<a {id_markup} href="{slide_or_href}">{text}</a>')
        else:
            self.current_update[item_id] = text

    def code(self, text, language='python'):
        _, id_markup = self._get_unique_id("code")
        content = fix_indent(text)

        if self._mode == ShowMode.Markup:
            self.current_content.append(f'<div {id_markup}><pre><code class="{language}">{content}</pre></code></div>')
        # else:
        #     self.current_update[item_id] = markdown(content)

    def animation(self, steps=10, time=0.1, loop=True):
        item_id, id_markup = self._get_unique_id('animation')

        if self._mode == ShowMode.Markup:
            self.current_content.append(f'<animation {id_markup} data-steps="{steps}" data-time="{time}" data-loop="{loop}"></animation>')
            self._global_values[item_id] = Animation(steps, time, loop)

        return self._global_values[item_id]

    def columns(self, *widths):
        return Column(self, *widths)

    def vertical(self):
        return Vertical(self)

    def fragment(self, style='fade-in'):
        return Fragment(self, style)

    def block(self, title="", style='default'):
        return Block(self, title, style)

    def success(self, title=""):
        return self.block(title, 'success')

    def warning(self, title=""):
        return self.block(title, 'warning')

    def error(self, title=""):
        return self.block(title, 'error')

    ## Internal API

    def do_markup(self, slide):
        self._mode = ShowMode.Markup
        self.current_content.clear()
        self._run(slide)
        return "\n\n".join(self.current_content)

    def do_code(self, slide):
        self._mode = ShowMode.Code
        self.current_update.clear()
        self._run(slide)
        return self.current_update

    ## Utilities

    def _run(self, slide):
        self._unique_id = 0
        self.current_slide = slide
        func = self.slides[slide]

        if func.__doc__:
            self.markdown(func.__doc__)

        func()

    def _get_unique_id(self, markup):
        self._unique_id += 1
        item_id = f"{self.current_slide}-{markup}-{self._unique_id - 1}"
        return item_id, f'id="{item_id}" data-slide="{self.current_slide}"'

    def render(self, theme='white'):
        return self._template.render(show=self, theme=theme)

    ## Routes

    async def _update(self, request):
        data = request.json

        if data['type'] == 'input':
            self._global_values[data['id']] = data['value']
        elif data['type'] == 'animation':
            self._global_values[data['id']].next()

        self.do_code(data['slide'])
        return json(self.current_update)

    async def _index(self, request):
        theme = request.args.get("theme", self.theme)
        return html(self.render(theme))
