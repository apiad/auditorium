# coding: utf8

import jinja2
from flask import Flask, render_template, send_from_directory


class Show(Flask):
    def __init__(self, *args, **kwargs):
        super(Show, self).__init__(*args, **kwargs)
        self.slides = []
        self.route("/")(self.index)
        self.route("/static/<path:filename>")(self.static)

    def slide(self, func):
        self.slides.append(func)

    def index(self):
        return render_template("index.html", show=self)

    def static(self, filename):
        return send_from_directory("static", filename)
