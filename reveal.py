# coding: utf8

import jinja2
from flask import Flask, render_template, send_from_directory


class Show(Flask):
    def __init__(self, *args, **kwargs):
        super(Show, self).__init__(*args, **kwargs)
        self.slides_md = {}
        self.slides_func = {}
        self.route("/")(self._index)
        self.route("/static/<path:filename>")(self._serve_static)

    def slide(self, func):
        self.slides_func[func.__name__] = func
        self.slides_md[func.__name__] = fix_docstring(func.__doc__)

    def _index(self):
        return render_template("index.html", slides=self.slides_md)

    def _serve_static(self, filename):
        return send_from_directory("static", filename)


def fix_docstring(docstring):
    lines = docstring.split("\n")
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
