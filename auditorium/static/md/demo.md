# Auditorium

### A demo for the "pure markdown" mode

## Static content

Static content can be added with pure markdown.

* Some _markdown_ content.
* More **markdown** content.

## And some Python

If you need interaction or advanced features,
add a code section with tag [`python :run`].

```python :echo :run
with show.columns(2) as cl:
    text = show.text_input("World")
    cl.tab()
    show.markdown(f"Hello {text}")
```

An instance named `show` will be magically available.

## Context

By default local variables created in a Python
block are **not** persisted. If you want to change this,
use `:persist`.

```python :echo :run :persist
cl = show.columns(2)
text = show.text_input("World")
# cl and text persist
```

```python :run :echo
cl.tab()
show.markdown(f"Hello {text}")
# don't forget cl.end()
```

```python :run
cl.end()
```

## Markdown Variables

Persistent local variables are injected
into Markdown and can be interpolated inside the content.


```python :run :persist
cl = show.columns(2)
text = show.text_input("World")
cl.tab()
```

**Hello {text}**. This is _pure_ Markdown.

```python :run
cl.end()
```

<hr>

~~~md
```python :run :persist
text = show.text_input("World")
```

Hello {text}. This is is written in Markdown.
~~~
