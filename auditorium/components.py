# coding: utf8

from enum import IntEnum


class ShowMode(IntEnum):
    Edit = 0
    Markup = 1
    Code = 2


class Animation:
    def __init__(self, steps, time, loop, current):
        self.steps = steps
        self.time = time
        self.loop = loop
        self._current = current

    @property
    def current(self):
        return self._current

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class Wrapper:
    def __init__(self, ctx):
        self.ctx = ctx
        self.begin()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self.end()

    def begin(self):
        raise NotImplementedError()

    def end(self):
        raise NotImplementedError()


class Column(Wrapper):
    def __init__(self, ctx, *widths):
        if len(widths) == 1:
            widths = [1.0 / widths[0] for _ in range(widths[0])]

        total_width = sum(widths) + 0.01
        widths = [w / total_width for w in widths]

        self.widths = list(widths)
        super(Column, self).__init__(ctx)

    def begin(self):
        self.ctx.content.append(f'<div class="columns">')
        self.ctx.content.append(
            f'<div class="column" style="width: {self.widths[0] * 100}%;">'
        )
        self.widths.pop(0)

    def tab(self):
        self.ctx.content.append(f"</div>")
        self.ctx.content.append(
            f'<div class="column" style="width: {self.widths[0] * 100}%;">'
        )
        self.widths.pop(0)

    def end(self):
        self.ctx.content.append("</div>")
        self.ctx.content.append("</div>")


class Block(Wrapper):
    def __init__(self, ctx, title, style):
        self.title = title
        self.style = style
        super(Block, self).__init__(ctx)

    def begin(self):
        self.ctx.content.append(
            f'<div class="block block-{self.style}"><h1 class="block-title">{self.title}</h1><div class="block-content">'
        )

    def end(self):
        self.ctx.content.append("</div></div>")


class Fragment(Wrapper):
    def __init__(self, ctx, style):
        self.style = style
        super(Fragment, self).__init__(ctx)

    def begin(self):
        self.ctx.content.append(f'<div class="fragment {self.style}">')

    def end(self, *args):
        self.ctx.content.append("</div>")
