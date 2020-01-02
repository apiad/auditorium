# Hosting your slideshow

If you are presenting on a big screen connected to your own computer, all you need to do is
`auditorium run [file]`, and you can present from [localhost:6789](http://localhost:6789) as usual.

However, there are many cases where you are either not presenting from your computer, or you want
to host your slideshow publicly for others to follow. Here are some ideas.

## Hosting on a local network

If the audience can ping your computer, then the easiest solution to
simply do:

```bash
auditorium run [file] --host=0.0.0.0
```
Then give them your public IP address. In Linux, run `ip addr` to see it.

## Hosting freely with `auditorium publish`

If your audience cannot reach you on the local network, or the computer
where the slideshow runs is not the one where you will be presenting, then
you need a way to proxy your slideshow to a public URL.

Enter `auditorium publish`, a command (and related service) that will relay
your slideshow to [auditorium.apiad.net](http://auditorium.apiad.net).
The slideshow still runs on your computer, but it is connected through websockets
with a server that renders the slide and proxies all incoming requests back to your machine.

To use it, simple run:

```bash
auditorium publish [file] --name [your-slideshow-name]
```

Then head over to `http://auditorium.apiad.net/your-slideshow-name/` and enjoy!

> **NOTE:** This service is provided as-is with no guarantees whatsoever. The service runs
> on a development server that is restarted often (at least twice a day), so slideshows are **not** guaranteed to stay
> up for a long time. Don't use this service in mission critical presentations.

If you need finer control then you can host the server yourself on your own infrastructure
and thus ensure that it's online when you need it. Just run:

```bash
auditorium server [--host HOST] [--port PORT]
```

Make sure the server is publicly accessible. You'll probably use some kind of web server,
or `--host 0.0.0.0` and `--port 80` which you can totally do since `auditorium` ships
with `uvicorn` which is a fully fledged production web server.
Then publish to your own address with:

```bash
auditorium publish [file] --name [name] --server [ws://your-server:port] # or wss://
```

## Hosting temporarily through `ngrok`

Another option is to use [`ngrok`](https://ngrok.com/).
It creates a tunnel between your computer and ngrok's servers, and gives you a public, secure (HTTPS)
and free URL that back-tunnels to your `localhost:port`.

It's very [easy to setup](https://ngrok.com/docs). Once `ngrok` is installed, just run the
usual `auditorium run [file]` and in another terminal run:

```bash
ngrok http 6789
```

It will answer with a temporal, auto-generated URL that you can give the audience.
The upside is that everything is being run on your computer but published through a public
URL, which means anyone on the world can see it.
The downside is that it only works for as long as you have `ngrok` running.
Plus, every time you run it, it generates a different public URL.
The do have paid plans for securing a custom domain.

## Hosting static files at Github Pages

If your slideshow is purely static, then you ran run:

```bash
auditorium render [file] > index.html
```

Then upload the file to a Github repository.
Using [Github Pages](https://pages.github.com/) will allow you to
publicly serve this HTML anywhere in the world.
The downside is no animations or interactive logic.

## Hosting as serverless functions at `now.sh`

Another option is to host the static presentation and backend at [now.sh](https://now.sh).
If you don't know what [now.sh](https://now.sh) is, go and [read about it](https://zeit.co/docs) first.

This is actually how we host the demo at [auditorium-demo.apiad.net](https://auditorium-demo.apiad.net).
The [demo](https://github.com/apiad/auditorium/tree/master/demo) folder folder shows the layout you need to comply with for hosting a slideshow at [now.sh](https://now.sh), such that the backend logic works as well.

Make sure your `slideshow.py` (or whatever the name) slideshow file has the following line:

```python
from auditorium import Show

show = Show("My Awesome Show")
app = show.app # <--- This line
```

This will allow `now.sh` serverless functions to find your slideshow's underlying `fastapi` application, and automagically make the backend logic work. Make a folder for uploading to `now.sh`, let's call it `my-show` and an `api` folder inside.

```bash
mkdir -p /path/to/my-show/api
```

Render the HTML.

```bash
auditorium render /path/to/slideshow.py > /path/to/my-show/index.html
```

Have your `slideshow.py` copied to `my-show/api/update.py`

```bash
cp /path/to/slideshow.py /path/to/my-show/api/update.py
```

Add a `now.json` file with an adequate configuration. This one works for the demo (replace `name` with your name):

```json
{
    "name": "auditorium-demo",
    "rewrites": [
        { "source": "/", "destination": "/index.html" },
        { "source": "/update", "destination": "/api/update" }
    ]
}
```

Add a `requirements.txt` file with your requirements. This one works for the demo:

```ini
auditorium # This is basically mandatory :)
matplotlib # Stuff you use in your slides
```

Finally [install](https://zeit.co/docs#install-now-cli) and run `now` inside the `my-show` folder. If you are using the [development docker images](https://hub.docker.com/r/auditorium/auditorium-dev), `now` is already installed for you.
