# Auditorium

[<img alt="PyPI - License" src="https://img.shields.io/pypi/l/auditorium.svg">](https://github.com/apiad/auditorium/blob/master/LICENSE)
[<img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/auditorium.svg">](https://pypi.org/project/auditorium/)
[<img alt="PyPI" src="https://img.shields.io/pypi/v/auditorium.svg">](https://pypi.org/project/auditorium/)
[<img alt="Travis (.org)" src="https://img.shields.io/travis/apiad/auditorium/master.svg">](https://travis-ci.org/apiad/auditorium)
[<img alt="Codecov" src="https://img.shields.io/codecov/c/github/apiad/auditorium.svg">](https://codecov.io/gh/apiad/auditorium)
[<img alt="Gitter" src="https://img.shields.io/gitter/room/apiad/auditorium">](https://gitter.im/auditorium-slides/community)
[<img alt="Demo" src="https://img.shields.io/badge/demo-browse-blueviolet"></img>](https://auditorium-demo.apiad.net)

> A Python-powered slideshow creator with steroids.

See the demo at [auditorium-demo.apiad.net](https://auditorium-demo.apiad.net).

## Hosting a slideshow at `now.sh`

[<img alt="Made with Auditorium" src="https://img.shields.io/badge/made--with-auditorium-blue"></img>](https://apiad.net/auditorium)

This folder shows the layout you need to comply with for hosting a slideshow at [now.sh](https://now.sh), such that the backend logic works as well. If you don't know what [now.sh](https://now.sh) is, go and [read about it](https://zeit.co/docs) first.

In short, these are the basic steps:

1. Make sure your `slideshow.py` (or whatever the name) slideshow file has the following line:

```python
from auditorium import Show

show = Show("My Awesome Show")
app = show.app # <--- This line
```

This will allow `now.sh` serverless functions to find your slideshow's underlying `sanic` application, and automagically make the backend logic work.

2. Make a folder for uploading to `now.sh`, let's call it `my-show` and an `api` folder inside.

```bash
mkdir -p /path/to/my-show/api
```

3. Render the HTML.

```bash
auditorium render /path/to/slideshow.py > /path/to/my-show/index.html
```

4. Have your `slideshow.py` copied to `my-show/api/update.py`

```bash
cp /path/to/slideshow.py /path/to/my-show/api/update.py
```

5. Add a `now.json` file with an adequate configuration. This one works for the demo (replace `name` with your name):

```json
{
    "name": "auditorium-demo",
    "rewrites": [
        { "source": "/", "destination": "/index.html" },
        { "source": "/update", "destination": "/api/update" }
    ]
}
```

6. Add a `requirements.txt` file with your requirements. This one works for the demo:

```ini
auditorium==0.6.5 # This is basically mandatory :)
matplotlib==3.1.2 # Stuff you use in your slides
```

7. [Install](https://zeit.co/docs#install-now-cli) and run `now` inside the `my-show` folder.
