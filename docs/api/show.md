# The `Show` class

!!! warning
    This section is for advanced usage. Please read the [Quick Start](/quickstart/) guides first.

!!! note
    This section asumes a Python-first approach for simplicity.
    You can use all of `auditorium` features in a Markdown-first approach
    with [runnable code blocks](/quickstart/#markdown-first).

The `Show` class is the first class you will need to interact
with when using `auditorium`. All your slideshows begin with something like:

```python
from auditorium import Show

show = auditorium.Show("My Show Title")
```

## Creating slides

The most important use of your `show` instance is the `@slide` decorator, which
allows you to create slides. A slide is created by decorating a function (or actually any callable)
with `@show.slide` like this:

```python
@show.slide
def first_slide(ctx):
    # content
```

Everything that can be included **inside** a slide is discussed in the [Context](/api/context/) page.

!!! note
    Slides are sorted in the order in which they are declared in your Python script.

### Customizing slides

The `@slide` decorator can receive an optional parameter `id` to configure a specific slide.

```python
@show.slide(id="the-first-slide")
def first_slide(ctx):
    # content
```

The slide identifier is used in HTML as anchor for that slide. Hence, when running
the slideshow, the previous slide would be located at `http://localhost:6789/#/the-first-slide`.
If no `id` is provided the slide identifier is built from the callable `__name__` parameter,
hence in the previous example it would be located at `http://localhost:6789/#/first_slide`

!!! warning
    Note that when using additional parameters, you have to use the form `@show.slide(...)`
    with parenthesis, but when not using parameters, you can use the decorator directly as
    `@show.slide` without parenthesis.

Default slide ids are OK if you don't care about having those ugly underscores in your slide
anchors in HTML. In any case, you can always author your slideshow first and then add
pretty slide identifiers afterwards.

### Vertical slides

Vertical slides are an effective way to add "read-more" like content to a slideshow.
You can see them in action at <https://auditorium-demo.apiad.net/#/vertical_slides>.

Vertical slides are added *after* a main slide, using a modified form of the `@slide` decorator.
Instead of using `@show.slide` you use `@main_slide.slide` where `main_slide` is the actual
function (or any other callable) that corresponds to the main slide.

```python
@show.slide
def main_slide(ctx):
    # This will be a regular slide

@main_slide.slide
def vertical_1(ctx):
    # This one is vertical to `main_slide`

@show.slide
def other_slide(ctx):
    # This one is another main slide

@other_slide.slide
def vertical_2(ctx):
    # This one is vertical to `other_slide`

@other_slide.slide
def vertical_3(ctx):
    # This one is also vertical to `other_slide`,
    # under the previous (`vertical_2`)
```

!!! note
    Vertical slides can be declared at any moment *after* but not necesarily *under* the main slide.
    This allows you to organize all your main slides at the top of a script and then add vertical slides when
    you think is convenient.

## Running the show

Once all slides are in, you can run a show by calling directly the `show.run` method:

```python
show.run('localhost', 6789)
```

However, this method is actually **not recommended**. Instead it is *preferred* to use:

```bash
auditorium run /path/to/myshow.py [--host HOST] [--port PORT]
```

The second method is preferred because it is more aligned with other usages such as `auditorium publish`
and, in the future, we will add a `--reload` option to allow hot-reload when you save your slideshow.

!!! error
    When calling `run` you can get an error like:

        :::bash
        (!) You need `uvicorn` installed in order to call `run`.

    This means you didn't installed `uvicorn` when installing `auditorium`, which is necessary
    for actually serving the HTML. You can fix it by installing like this:

        pip install auditorium[server]

    Serverless installations are smaller and useful if you only want to use `render` or `publish`,
    or [deploy to a serverless cloud provider](/hosting/#hosting-as-serverless-functions-at-nowsh).

## Rendering the show

You can obtain a static HTML with embedded resources ready to be served with:

```python
static_html = show.render(theme="white")

with open("/path/to/myshow.html", "w") as fp:
    fp.write(static_html)
```

The reason why `render` returns a `string` rather than saving to a file is because you could
use this functionality in a serverless cloud provider or any other context where you cannot
interact directly with path-based files. It's up to you how to make use of the rendered HTML.

That said, if you use the [CLI command](/api/cli) `render` you can achieve this more easily with:

```python
auditorium render /path/to/myshow.py > /path/to/myshow.html
```

## Loading a show

The static method `Show.load` takes in a path and loads the corresponding show instance.

```python
show = Show.load("/path/to/show.py")
```

It works with both Python (`myshow.py`) and Markdown (`myshow.md`) file extensions.
It is useful in contexts where you can serve multiple slideshows, for example,
in a server context where you want to map URL paths to specific shows.

After calling `load` you receive a `Show` instance with all it can do.

## Appending multiple shows

You can build a slideshow in parts, some in Python, some in Markdown, and then
use `show.append` to connect them. It works with `Show` instances and path names as well.

```python
show = Show("Main Show")
# ... build show

# append another instance
other_show = Show("Other show")
# ... build other_show
show.append(other_show)

# append by path
show.append("/path/to/anothershow.py") # Python
show.append("/path/to/anothershow.md") # Markdown
```

This allows you to build a slideshow in parts. Maybe some slides are more
convenient in Markdown-first mode because they are mostly static content,
while a few specific slides are very tricky and it's better to code them in Python.

!!! warning
    This section is under construction. More content will be added shortly.
