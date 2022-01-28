from fastapi import FastAPI


class HTMLNode:
    def __init__(self, tag, app: FastAPI) -> None:
        self._tag = tag
        self._app = app