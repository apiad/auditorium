# coding: utf8

"""
This module includes the `Show` class and the main functionalities of `auditorium`.
"""

import base64
import io
from enum import Enum

import jinja2
from flask import Flask, jsonify, render_template, send_from_directory
from markdown import markdown


class ShowMode(Enum):
    Markup = 1
    Code = 2


class Show(Flask):
    def __init__(self, *args, **kwargs):
        super(Show, self).__init__(*args, **kwargs)
        self.slides = {}

        self.route("/")(self._index)
        self.route("/static/<path:filename>")(self._serve_static)
        self.route("/update/<slide>/<item_id>/<value>")(self._update)

        self.current_content = []
        self.current_update = {}
        self.current_slide = None
        self._unique_id = 0
        self._global_values = {}
        self._mode = ShowMode.Markup

    ## @slide decorator

    def slide(self, func):
        self.slides[func.__name__] = func
        return func

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

    def anchor(self, slide, text):
        item_id, id_markup = self._get_unique_id("anchor")

        if self._mode == ShowMode.Markup:
            self.current_content.append(f'<a {id_markup} href=#/{slide.__name__}>{text}</a>')
        else:
            self.current_update[item_id] = text

    def code(self, text):
        item_id, id_markup = self._get_unique_id("code")
        content = fix_indent(text, tab_size=4)

        if self._mode == ShowMode.Markup:
            self.current_content.append(f'<div {id_markup}>{markdown(content)}</div>')
        # else:
        #     self.current_update[item_id] = markdown(content)

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

    ## Utils

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

    ## Routes

    def _update(self, slide, item_id, value):
        self._global_values[item_id] = value
        self.do_code(slide)
        return jsonify(self.current_update)

    def _index(self):
        return render_template("index.html", show=self)

    def _serve_static(self, filename):
        return send_from_directory("static", filename)


def fix_indent(content, tab_size=0):
    lines = content.split("\n")
    min_indent = 1e50

    for l in lines:
        if not l or l.isspace():
            continue

        indent_size = 0

        for c in l:
            if c.isspace():
                indent_size += 1
            else:
                break

        min_indent = min(indent_size, min_indent)

    lines = [" " * tab_size + l[min_indent:] for l in lines]

    while lines and lines[0].isspace():
        lines.pop(0)

    return "\n".join(lines)
