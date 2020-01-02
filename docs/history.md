# History

### v19.1.5

* Fixed automatic server address for `auditorium publish`.

### v19.1.4

* Added command `auditorium server` that allows to proxy a slideshow through a public server.
* Added command `auditorium publish` for authors to publish their slides.
* Opened service at [auditorium.apiad.net](http://auditorium.apiad.net) (sorry, no HTTPS yet).

### v19.1.3

* Changed vertical slides API, now slides don't need to be run the first time the slideshow is loaded, since the entire slideshow is flat.

### v19.1.2

* Switched to [FastAPI](https://fastapi.tiangolo.com) 🤓🤓 !!

### v19.1.1

* To celebrate the new year we are switching to [calver](https://calver.org/) versioning for good!

### v0.6.4

* New development environment completely based on Docker.
* Added compatibility with Python 3.7 and 3.8.

### v0.6.3

* Added `Show.append` to append existing `show` instances or direct paths.
* Fixed error with absolute path for the Markdown demo.
* Append Markdown demo to the Python demo.

### v0.6.2

* Added `mypy` for some static type checking. Will slowly add as many type hints as possible.
* Fixed dependency bugs when porting to `poetry`.

### v0.6.1

* Changed package manager to `poetry`.

### v0.6.0

* Completely redesigned API. Now slide functions receive a `ctx: Context` instance on which to call all the layout options. This detaches the `Show` instance from the slides code, which makes `Show` a stateless object and all slide functions side-effects are contained for each client.

### v0.5.1

* Added `pygments` for code highlighting, removing `highlight.js` and fixing the error with static rendering.

### v0.5.0

* Added command `auditorium render` to generate a static HTML that can be displayed without `auditorium`.

### v0.4.5

*  Fixed random order of vertical slides.

### v0.4.4

*  Changed the syntax for vertical slides, thanks to suggestions by [@tialpoy](https://www.reddit.com/user/tialpoy/).
*  Added automatically launching browser on `auditorium run` and `... demo`. Override with `--launch=0`.
*  Improved performance, now rendering only occurs at `show.run` or when changing the theme.

### v0.4.3

*  Improved test coverage a lot.

### v0.4.2

*  Added support for interpolating Python variables in Markdown mode.

### v0.4.0

*  Ported to Sanic 🤓!

### v0.3.1

*  Improved support for running Markdown.

### v0.3.0

*  Added support for running directly from Markdown files with `auditorium run <file.md>`.

### v0.2.0

*  Added command `auditorium run <file.py>` for running a specific slideshow. This is now the preferred method.
*  Added command `auditorium demo` for running the demo.

### v0.1.5

*  Added support for `reveal.js` themes via `show.theme` and query-string argument `?theme=...`.
*  Improved testing coverage.
*  Fixed error with missing static files in the distribution package.

### v0.1.3

*  Added support for fragments.
*  Added support for vertical slides.
*  Added custom layout options with `show.columns`.
*  Added styled block with `show.block`.
*  Added parameter `language` for `show.code`, defaulting to `"python"`.
*  Improved layout for columns, with horizontal centering.
*  Improved layout for input texts.
*  Improved example for the `pyplot` support in the demo.
*  Fixed some style issues.
*  Fixed error reloading on a slide with an animation.
*  Updated Readme with some examples.

### v0.1.2

*  Refactor custom CSS and JavaScript into `auditorium.css` and `auditorium.js` respectively.

### v0.1.1

*  Added basic binding for variables.
*  Added support for simple animations with `show.animation`.
*  Added support for `pyplot` rendering.

### v0.1.0

*  Initial version with basic functionality.
