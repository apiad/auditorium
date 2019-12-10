# coding: utf8

import fire
import runpy
import webbrowser

from auditorium.markdown import MarkdownLoader


class Auditorium:
    @staticmethod
    def run(path, host='localhost', port=6789, debug=False, instance_name='show'):
        "Runs a custom Python script as a slideshow."

        if path.endswith('.py'):
            ns = runpy.run_path(path)
            show = ns[instance_name]
        elif path.endswith('.md'):
            loader = MarkdownLoader(path, instance_name=instance_name)
            show = loader.parse()

        show.run(host=host, port=port, debug=debug)
        # webbrowser.open_new_tab(f"{host}:{port}")

    @staticmethod
    def demo(host='localhost', port=6789, debug=False):
        "Starts the demo slideshow."

        from auditorium.demo import show
        show.run(host, port, debug=debug)


def main():
    fire.Fire(Auditorium, name='auditorium')


if __name__ == "__main__":
    main()
