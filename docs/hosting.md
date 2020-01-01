# Hosting Options

## Hosting a slideshow at `now.sh`

Another option is to host the static presentation and backend at [now.sh](https://now.sh).
If you don't know what [now.sh](https://now.sh) is, go and [read about it](https://zeit.co/docs) first.
The [demo](https://github.com/apiad/auditorium/tree/master/demo) folder folder shows the layout you need to comply with for hosting a slideshow at [now.sh](https://now.sh), such that the backend logic works as well.

In short, these are the basic steps:

1. Make sure your `slideshow.py` (or whatever the name) slideshow file has the following line:

```python
from auditorium import Show

show = Show("My Awesome Show")
app = show.app # <--- This line
```

This will allow `now.sh` serverless functions to find your slideshow's underlying `fastapi` application, and automagically make the backend logic work.

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
auditorium # This is basically mandatory :)
matplotlib # Stuff you use in your slides
```

7. [Install](https://zeit.co/docs#install-now-cli) and run `now` inside the `my-show` folder. If you are using the [development docker images](https://hub.docker.com/r/auditorium/auditorium-dev), `now` is already installed for you.
