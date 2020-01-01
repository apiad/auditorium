# Quick Start

## Python First

In `auditorium` you create a presentation via the `Show` class:

```python
# Content of <file.py>

from auditorium import Show
show = Show("My Show")
```

Every slide in your show is a Python method that renders the content and powers the backend logic.
Slides are decorated with the `@show.slide` decorator.
Every slide receives a `ctx` parameter, of type `Context`, which provides the functionalities
that add content, both static and reactive.

```python
@show.slide
def one_slide(ctx):
    # content
```

Then run the show:

```bash
auditorium run <file.py>
```

> **Slides are ordered in the same order in which methods are defined in your script.**

Optionally, you can specify `--host` and `--port` as well as `--debug` which activates hot-reload and outputs debug info (powered by Sanic).

Alternatively, you can also directly call `show.run`, although the recommended way is the previous one.

```python
show.run('localhost', 6789)
```

The simplest possible form of content is static Markdown.
You can add it directly as the docstring of the corresponding slide function,
or calling `ctx.markdown`.

```python
@show.slide
def static_content(ctx):
    """
    ## Static content

    Can be added very simply with:

    * Method _docstrings_
    * Calling `show.markdown`
    """

    ctx.markdown("> Like this")
```

There are several components in `auditorium` to style and layout your presentation, including reactive components that respond to user input.

```python
@show.slide
def interactive(ctx):
    ctx.markdown("Enter your name")
    name = ctx.text_input(default="World")
    ctx.markdown(f"> Hello {name}")
```

The slide code is considered stateless, and will be executed every time the input changes.
You should design your slides with this in mind to, for example, provide sensible default values that will work when your presentation first opens.

Simple stateless animations can be created with `ctx.animation`, which execute the backend code for every frame.
Combining this with drawing logic from, for example, `matplotlib` allows for very simple animated graphs and visualizations:

```python
@show.slide
def pyplot(ctx):
    with ctx.animation(steps=50, time=0.33, loop=True) as anim:
        # Every 0.33 seconds the graph will move
        step = anim.current * 2 * math.pi / 50
        x = np.linspace(0, 2 * math.pi, 100)
        y = np.sin(x + step) + np.cos(x + step)
        plt.plot(x, y)
        plt.ylim(-2,2)
        ctx.pyplot(plt, fmt='png', height=350)
```

## Markdown First

Alternatively, if you need little to no Python, you can author your slideshow in pure Markdown. Every level-2 header (`##`) becomes a slide.

```markdown
## Static content

Static content can be added with pure markdown.

*  Some _markdown_ content.
*  More **markdown** content.
```

Pure Markdown can be used as long as all you need is static content. If you need more advanced features, you can add a Python code section anywhere in your slideshow and it will be executed.

~~~markdown
## Dynamic content

If you need interaction or advanced `auditorium` features,
simply add a code section.

```python :run
with ctx.columns(2) as cl:
    text = ctx.text_input("World")

    cl.tab()

    with ctx.success("Message"):
        ctx.markdown(f"Hello {text}")
```
~~~

An instance named `ctx` will be magically available in every Python code section. Beware that **local variables are not persisted** between different code sections. This is a by-design decision to save you a bunch of headaches, believe me.
If you want variables to persist across code sections, add `:persist` in the code declaration section. This also let's you interpolate Python variables directly inside the Markdown content.

~~~markdown
```python  :run :persist
text = ctx.text_input("World")
```

Hello {text}. This is pure Markdown.
~~~

You need to add `:run` to the code section declaration for it to be executed, otherwise `auditorium` will consider it just Markdown code and simply print it. If you want **both** to run and print the code, then add `:run` and `:echo` to the code declaration part.

Once you finished authoring you slideshow, simply run it just like before:

```bash
auditorium run <file.md>
```

If you want to see an example, [check here](https://github.com/apiad/auditorium/raw/master/auditorium/static/md/demo.md).

## Going full static

If you only need `auditorium` to generate the HTML, but have no interactive code whatsoever, you can also run:

```bash
auditorium render <file.[py|md]> > <output.html>
```

This will render the slideshow in an HTML file with all CSS and JavaScript embedded. Just copy this single HTML file and open it on any browser. You won't need to have `auditorium` installed. However, do keep in mind that all of the backend code will execute only once for the initial rendering, so your animations will be frozen at the starting frame and none of the interaction will work.
