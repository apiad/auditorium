# coding: utf8

import jinja2
from flask import Flask, render_template, send_from_directory
from markdown import markdown


class Show(Flask):
    def __init__(self, *args, **kwargs):
        super(Show, self).__init__(*args, **kwargs)
        self.slides = {}
        self.route("/")(self._index)
        self.route("/static/<path:filename>")(self._serve_static)
        self.current_content = []

    def slide(self, func):
        self.slides[func.__name__] = func

    def markdown(self, content):
        self.current_content.append(markdown(fix_indent(content)))

    def do_markup(self, slide):
        self.current_content.clear()
        self.slides[slide]()
        return "\n\n".join(self.current_content)

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
