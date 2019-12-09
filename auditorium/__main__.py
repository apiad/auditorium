# coding: utf8

import fire


class Auditorium:
    @staticmethod
    def run(script):
        print(script)

    @staticmethod
    def demo(host='localhost', port=6789, debug=False):
        from auditorium.demo import show
        show.run(host, port, debug=debug)


if __name__ == "__main__":
    fire.Fire(Auditorium, name='auditorium')
