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
