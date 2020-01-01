# coding: utf8

import fire
import runpy
import webbrowser

from auditorium import Show


class Auditorium:
    @staticmethod
    def run(
        path,
        *,
        host: str = "127.0.0.1",
        port: int = 6789,
        debug: bool = False,
        instance_name: str = "show",
    ):
        "Runs a custom Python script as a slideshow."

        show = Show.load(path, instance_name)
        show.run(host=host, port=port, debug=debug)

    @staticmethod
    def publish(
        path: str,
        name: str,
        *,
        server: str = "wss://auditorium.apiad.net",
        instance_name: str = "show"
    ):
        show = Show.load(path, instance_name)
        show.publish(server=server, name=name)

    @staticmethod
    def demo(host: str = "127.0.0.1", port: int = 6789, debug: bool = False):
        "Starts the demo slideshow."

        from auditorium.demo import show

        show.run(host=host, port=port, debug=debug)

    @staticmethod
    def render(path, theme="white", instance_name="show"):
        "Renders a slideshow into a single HTML with all resources embedded."

        show = Show.load(path, instance_name)
        print(show.render(theme))

    @staticmethod
    def server(host: str = "0.0.0.0", port: int = 9876):
        from auditorium.server import run_server

        run_server(host=host, port=port)

    @staticmethod
    def test():
        return "It's OK!"


def main():
    fire.Fire(Auditorium, name="auditorium")


if __name__ == "__main__":
    main()
