# Auditorium

### A demo for the "pure markdown" mode

## Static content

Static content can be added with pure markdown.

* Some _markdown_ content.
* More **markdown** content.

## And some Python

If you need interaction or advanced `auditorium` features,
simply add a code section.

```python
with show.columns(2) as cl:
    text = show.text_input("World")

    cl.tab()

    with show.success("Message"):
        show.markdown(f"Hello {text}")
```

An instance named `show` will be magically available.
