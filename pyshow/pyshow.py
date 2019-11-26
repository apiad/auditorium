# coding: utf8

import jinja2
from flask import Flask, render_template, send_from_directory, jsonify
from markdown import markdown
from enum import Enum

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

    ## Binding methods

    def markdown(self, content):
        item_id, id_markup = self._get_unique_id("markdown")

        if self._mode == ShowMode.Markup:
            self.current_content.append(f'<div {id_markup}>{markdown(fix_indent(content))}</div>')
        else:
            self.current_update[item_id] = markdown(fix_indent(content))

    def text_input(self, default=""):
        item_id, id_markup = self._get_unique_id("text-input")

        if self._mode == ShowMode.Markup:
            self.current_content.append(f'<input {id_markup} type="text" class="text" value="{default}"></input>')
            self._global_values[item_id] = default
            return default
        else:
            print("item_id", item_id)
            return self._global_values[item_id]

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
        self.slides[slide]()

    def _get_unique_id(self, markup):
        self._unique_id += 1
        item_id = f"{self.current_slide}-{markup}-{self._unique_id - 1}"
        return item_id, f'id="{item_id}" data-slide="{self.current_slide}"'

    ## Routes

    def _update(self, slide, item_id, value):
        self._global_values[item_id] = value
        print(self._global_values)
        self.do_code(slide)
        return jsonify(self.current_update)

    def _index(self):
        return render_template("index.html", show=self)

    def _serve_static(self, filename):
        return send_from_directory("static", filename)


def fix_indent(content):
    lines = content.split("\n")
    min_indent = 1e50

    for l in lines:
        if not l:
            continue

        indent_size = 0

        for c in l:
            if c.isspace():
                indent_size += 1
            else:
                break

        min_indent = min(indent_size, min_indent)

    lines = [l[min_indent:] for l in lines]
    return "\n".join(lines)
