# Where is the catch?

Auditorium covers a fairly simple use case that I haven't seen solved for a long time.
I came up with this idea while trying to make better slideshows for my lectures at the University of Havana.
I usually need to display complex math stuff and graphs, ideally animated, and sometimes make modifications on the fly according to the interaction with students.
They could ask how a function would look if some parameters where changed, etc.

Along that path I grew up from Power Point to JavaScript-based slides (like [reveal.sj](https://revealjs.com)) and sometimes even coded some simple behavior in JS, like changing a chart's parameters.
However, for the most complex stuff I wanted to use Python, because otherwise I would need to redo a lot of coding in JS.
For example, I'm teaching compilers now, and I want to show interactively how a parse tree is built for a regular expression.
I simply cannot rewrite my regex engine in JS just for a slideshow.

Then I discovered [streamlit](https://streamlit.io) and for a while tried to move my slides to streamlit format.
Streamlit is awesome, but is aimed at a completely different use case.
It's quite cumbersome to force it to behave like a slideshow, the flow is not natural, and the styling options are very restrictive.
On the other hand, they handle a lot of complex scenarios which I simply don't need in a slideshow, like caching and a lot of magic with Pandas and Numpy.
Contrary to streamlit, I do want custom CSS and HTML to be easy to inject, because styling is very important in slides.

So I decided to write my own slideshow generator, just for my simple use cases.
That being said, there are some known deficiencies that I might fix, and some others which I probably will not, even in the long run.

## Slides need to be fast

A slide's code is executed completely every time that slide needs to be rendered.
That is, once during the initial rendering and then when inputs change or animations tick.
Hence, you slide logic should be fairly fast.
This is particularly true for animations, so don't expect to be able to train a neural network in real time.
The slide logic is meant to be simple, the kind of one-liners you can run every keystroke, in the order of a couple hundred miliseconds at most.
If you need to interactively draw the loss value of a neural network, either is gonna take a while or you will have to fake it, i.e., compute it offline and then simply animate it.

## Slides have to be stateless

The code that runs inside a slide should not depend on anything outside of `ctx`, since you have no guarantee when will it be executed.
Right now, slide's code is executed once during the
initial rendering to layout and then everytime an interaction or animation forces the slide to render again.
However, this might be changed at any time, so make no assumptions as to when is that code executed.
The easiest way to do this, is making sure that every slide function is a pure function and all state is handled through
`ctx` interactive items, such as `ctx.text_input`.

## Watch out for code injection!

It is very tempting to do things like getting a text from an input box and passing it through `eval` in Python, so that you can render different functions interactively.
As long as you serve your presentations on `localhost` and show them yourself, feel free.
However, beware when hosting presentations online.
Since the backend code runs in your computer, a viewer could inject nasty stuff such as importing `os` and deleting your home folder! In the future I might add a `--safe` option that only allows for animations and other interactive behaviors that don't use input directly from the user.
Staying away from `eval` and `exec` should keep you safe in most scenarios, but the basic suggestion is don't do anything you wouldn't do in a regular web application, since all security issues are the same.
