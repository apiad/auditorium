# coding: utf8

import fire
import runpy
import webbrowser

from auditorium import Show


class Auditorium:
    @staticmethod
    def run(
        path,
        host="localhost",
        port=6789,
        debug=False,
        instance_name="show",
        launch=True,
    ):
        "Runs a custom Python script as a slideshow."

        show = Show.load(path, instance_name)
        show.run(host=host, port=port, debug=debug, launch=launch)

    @staticmethod
    def demo(host="localhost", port=6789, debug=False, launch=True):
        "Starts the demo slideshow."

        from auditorium.demo import show

        show.run(host, port, debug=debug, launch=launch)

    @staticmethod
    def render(path, theme="white", instance_name="show"):
        "Renders a slideshow into a single HTML with all resources embedded."

        show = load(path, instance_name)
        print(show.render(theme))


def main():
    fire.Fire(Auditorium, name="auditorium")


if __name__ == "__main__":
    main()
