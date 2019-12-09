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


def main():
    fire.Fire(Auditorium, name='auditorium')


if __name__ == "__main__":
    main()
