# coding: utf8

import fire
import runpy


class Auditorium:
    @staticmethod
    def run(path, host='localhost', port=6789, debug=False, instance_name='show'):
        "Runs a custom Python script as a slideshow."

        ns = runpy.run_path(path)
        show = ns[instance_name]
        show.run(host=host, port=port, debug=debug)

    @staticmethod
    def demo(host='localhost', port=6789, debug=False):
        "Starts the demo slideshow."

        from auditorium.demo import show
        show.run(host, port, debug=debug)


def main():
    fire.Fire(Auditorium, name='auditorium')


if __name__ == "__main__":
    main()
