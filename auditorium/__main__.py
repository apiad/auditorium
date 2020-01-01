# coding: utf8

import fire
import runpy
import webbrowser

from auditorium import Show


class Auditorium:
    @staticmethod
    def run(
        path,
        host: str = "127.0.0.1",
        port: int = 6789,
        debug: bool = False,
        instance_name: str = "show",
        server: str = None,
        name: str = None,
    ):
        "Runs a custom Python script as a slideshow."

        show = Show.load(path, instance_name)

        if server is None:
            show.run(host=host, port=port, debug=debug)
        else:
            if name is None:
                print("Error: must supply --name when using --server")
                exit(1)

            show.run_server(server=server, name=name)

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
