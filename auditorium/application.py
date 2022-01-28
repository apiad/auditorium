from fastapi import FastAPI

from auditorium.dom import HTMLNode


class Application:
    def __init__(self) -> None:
        self._app = FastAPI()
        self.dom = HTMLNode("html", self._app)