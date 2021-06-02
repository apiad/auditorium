from asyncio.exceptions import CancelledError
import typer
import asyncio
from auditorium import Show
from traceback import print_exc

from pathlib import Path
from runpy import run_path


app = typer.Typer(name="auditorium")


async def main(path: Path, host: str, port: int, instance: str, reload: bool):
    last_time = path.stat().st_mtime
    ns = run_path(str(path))
    show: Show = ns[instance]

    if not reload:
        await show.run(host, port)
        return

    task = asyncio.create_task(show.run(host, port))

    while True:
        await asyncio.sleep(0.1)

        current_time = path.stat().st_mtime

        if task.done():
            break

        if current_time == last_time:
            continue

        await show.stop()
        print("Reloading...")

        last_time = current_time

        try:
            ns = run_path(str(path))
            show: Show = ns[instance]
            task = asyncio.create_task(show.run(host, port))
        except Exception as e:
            print_exc()
            print("Waiting for file modification to reload...")


@app.command("run")
def run(
    path: Path,
    host: str = "127.0.0.1",
    port: int = 8000,
    instance: str = "show",
    reload: bool = False,
):
    if not path.exists():
        raise ValueError(f"Path {path} is invalid")

    asyncio.run(main(path, host, port, instance, reload))


@app.command("render")
def render(path: Path):
    pass


if __name__ == "__main__":
    app()
