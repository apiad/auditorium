# coding: utf8

from enum import IntEnum

class ShowMode(IntEnum):
    Markup = 1
    Code = 2


class Animation:
    def __init__(self, steps, time, loop):
        self.steps = steps
        self.time = time
        self.loop = loop
        self._current = 0

    @property
    def current(self):
        return self._current

    def next(self):
        self._current += 1

        if self._current >= self.steps:
            if self.loop:
                self._current = 0
            else:
                self._current = self.steps - 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class Column:
    def __init__(self, show, *widths):
        if len(widths) == 1:
            widths = [1.0/widths[0] for _ in range(widths[0])]

        total_width = sum(widths) + 0.01
        widths = [w/total_width for w in widths]

        self.widths = list(widths)
        self.show = show

    def __enter__(self):
        self.show.current_content.append(f'<div class="columns">')
        self.show.current_content.append(f'<div class="column" style="width: {self.widths[0] * 100}%;">')
        self.widths.pop(0)
        return self

    def tab(self):
        self.show.current_content.append(f'</div>')
        self.show.current_content.append(f'<div class="column" style="width: {self.widths[0] * 100}%;">')
        self.widths.pop(0)

    def __exit__(self, *args, **kwargs):
        self.show.current_content.append('</div>')
        self.show.current_content.append('</div>')


class Vertical:
    def __init__(self, show):
        self.show = show

    def __enter__(self):
        self.show.slide_ids.append("show::start-section")
        return self

    def __exit__(self, *args, **kwargs):
        self.show.slide_ids.append("show::end-section")


class Block:
    def __init__(self, show, title, style):
        self.show = show
        self.title = title
        self.style = style

    def __enter__(self):
        self.show.current_content.append(f'<div class="block block-{self.style}"><h1 class="block-title">{self.title}</h1><div class="block-content">')
        return self

    def __exit__(self, *args):
        self.show.current_content.append('</div></div>')


class Fragment:
    def __init__(self, show, style):
        self.show = show
        self.style = style

    def __enter__(self):
        self.show.current_content.append(f'<div class="fragment {self.style}">')
        return self

    def __exit__(self, *args):
        self.show.current_content.append('</div>')
