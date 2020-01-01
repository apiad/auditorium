# coding: utf8

import warnings
import websockets

from typing import Dict, Tuple
from fastapi import FastAPI, HTTPException
from starlette.responses import HTMLResponse
from starlette.websockets import WebSocket
import asyncio
from jinja2 import Template

from .utils import path
from .show import UpdateData

server = FastAPI()

SERVERS: Dict[str, Tuple[asyncio.Queue, asyncio.Queue]] = {}

with open(path('templates/server.html')) as fp:
    TEMPLATE = Template(fp.read())


@server.get("/")
async def index():
    return HTMLResponse(TEMPLATE.render(servers_list=list(SERVERS)))


@server.get("/{name}/")
async def render(name: str):
    try:
        queue_in, queue_out = SERVERS[name]
    except KeyError:
        raise HTTPException(404)

    await queue_in.put(dict(type="render"))

    response = await queue_out.get()
    queue_out.task_done()

    return HTMLResponse(response["content"])


@server.post("/{name}/update")
async def update(name: str, data: UpdateData):
    try:
        queue_in, queue_out = SERVERS[name]
    except KeyError:
        raise HTTPException(404)

    await queue_in.put(data.dict())

    response = await queue_out.get()
    queue_out.task_done()

    return response


@server.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    name = await websocket.receive_text()

    if name in SERVERS:
        await websocket.send_json(dict(type="error", msg="Name is already taken."))
        await websocket.close()
        return

    print("Registering new server: ", name)

    queue_in: asyncio.Queue = asyncio.Queue()
    queue_out: asyncio.Queue = asyncio.Queue()

    SERVERS[name] = (queue_in, queue_out)

    try:
        while True:
            command = await queue_in.get()
            await websocket.send_json(command)
            response = await websocket.receive_json()

            queue_in.task_done()
            await queue_out.put(response)
    except:
        print("(!) Connection to %s closed by client." % name)

        for _ in range(queue_in.qsize()):
            queue_in.task_done()

        for _ in range(queue_out.qsize()):
            queue_out.task_done()

    print("Unregistering server:", name)
    SERVERS.pop(name)


def run_server(*, host="0.0.0.0", port=9876):
    try:
        import uvicorn

        uvicorn.run(server, host=host, port=port)
    except ImportError:
        warnings.warn("(!) You need `uvicorn` installed in order to call `server`.")
        exit(1)
