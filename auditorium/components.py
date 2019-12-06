# coding: utf8


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
