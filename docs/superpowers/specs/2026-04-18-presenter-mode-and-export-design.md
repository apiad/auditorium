# Presenter Mode + Export

## Overview

Two independent features for the v3.0 release cycle:

1. **Presenter mode** — a second browser tab showing notes, timer, slide mirror, and next-slide preview. Comes with a breaking change: docstrings become private presenter notes, not slide content.
2. **`auditorium export`** — render the final state of each slide and produce a PDF, self-contained HTML, or PNG set.

These are independent and can ship separately, but the docstring change (presenter mode) is a breaking major version bump, so both should ship as v3.0 together.

---

## Feature 1: Presenter Mode

### Breaking change: docstrings are notes

Docstrings on `@deck.slide` functions stop rendering as visible slide content. They become private presenter notes, shown only in the presenter view. All visible content must come from `md()`, `show()`, and other vocabulary calls in the function body.

This simplifies the mental model: docstring = what you say, function body = what the audience sees.

**Migration:** Existing decks need to move docstring content into `md()` calls. `demo_deck.py` must be updated. Bump to v3.0.

### How it works

The presenter view is a second HTML page served at `/presenter`. It connects via websocket like any other client, but receives additional message types for notes and next-slide info.

**Opening it:**
- `auditorium run deck.py --presenter` auto-opens two tabs: audience + presenter
- Pressing `p` in the audience view opens `/presenter` in a new tab
- The presenter URL is `http://localhost:PORT/presenter`

### Presenter view layout

```
+------------------------------------------+------------------+
|                                          |                  |
|                                          |   NOTES          |
|          CURRENT SLIDE                   |   (docstring     |
|          (mirror of audience)            |    as markdown)  |
|                                          |                  |
|                                          +------------------+
|                                          |                  |
|                                          |   NEXT SLIDE     |
|                                          |   Title + first  |
|                                          |   paragraph of   |
+------------------------------------------+   docstring      |
                                           +------------------+
                                           |  12:34   3 / 11  |
                                           +------------------+
```

- **Left (large):** mirror of the current slide. Receives the same DOM mutations as the audience session.
- **Right top:** current slide's docstring rendered as markdown.
- **Right middle:** next slide's function name (as title) and first paragraph of its docstring. This is static metadata — no function execution required.
- **Right bottom:** elapsed timer (MM:SS, client-side JS) and slide N/M indicator.

### Server changes

**Notes delivery:** When `_run_slide` starts a slide, it sends:

```json
{"type": "notes", "html": "<rendered docstring markdown>"}
```

This is sent to all sessions (both audience and presenter parse it — audience ignores it, presenter displays it).

**Next-slide preview:** Alongside the notes, send:

```json
{"type": "next_preview", "title": "slide_function_name", "excerpt": "<first paragraph of next slide's docstring>"}
```

If the current slide is the last one, `next_preview` has `title: null`.

**Docstring no longer renders as content:** In `_run_slide`, remove the block that calls `ctx.md(slide_fn.func.__doc__)`. The docstring is only sent via the `notes` message.

### Client changes

**Audience view (`index.html`):** No change to mutation handling. Just ignores `notes` and `next_preview` messages. Add a keypress handler for `p` that opens `/presenter` in a new tab.

**Presenter view (`presenter.html`):** New HTML file. Two-pane layout (CSS grid or flexbox). Left pane has a `#slide-root` that receives mutations. Right pane has `#notes`, `#next-preview`, and `#timer` divs. The websocket handler routes `notes` and `next_preview` messages to the right pane.

**Timer:** Pure client-side. Starts on first `slide` message. Shows `MM:SS` elapsed. Not synced to server.

### Navigation

Both audience and presenter tabs can send keypresses. Since sessions are per-tab, pressing right arrow in the presenter tab only advances that tab's session. To keep them in sync, the presenter tab should NOT run its own session — instead it should share the audience session.

**Approach:** The presenter view connects with `{"type": "hello", "slide": 0, "role": "presenter"}`. The server creates a `Session` with `role="presenter"`. When a non-presenter session navigates, the server broadcasts the mutations to all presenter sessions too. Or simpler: the presenter is just another independent session — the presenter navigates and the audience tab is passive (read-only, no keypress capture unless it's the only tab).

**Recommended:** Keep it simple — both tabs are independent sessions. The presenter drives the talk from their presenter tab. The audience tab is opened separately (by the projector, by students, etc.) and navigates independently or is driven by a separate mechanism later.

---

## Feature 2: `auditorium export`

### CLI

```
auditorium export deck.py [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--format` / `-f` | `pdf` | Output format: `pdf`, `html`, `png` |
| `--output` / `-o` | `deck.pdf` / `deck.html` / `slides/` | Output path |
| `--resolution` | `1920x1080` | Viewport size |

### How it works

Same infrastructure as `auditorium record`: start server programmatically, launch headless Playwright, navigate slides. But instead of video capture:

1. For each slide: load it with `auto_step=0` (steps resolve instantly) and `slide_delay=0` (no linger). Wait for the slide function to complete.
2. Capture the final state based on format.
3. Advance to the next slide. Repeat.

### Format: PDF (vector)

Use Playwright's `page.pdf()` which produces vector PDF output — text remains selectable, math renders as paths, no rasterization.

For each slide:
1. Wait for slide to finish rendering.
2. Call `page.pdf()` with the viewport dimensions as page size.
3. Collect all single-page PDFs.
4. Merge into one multi-page PDF (using `pypdf` or similar, or by reloading each slide on the same page and printing once with page breaks).

**Simpler approach:** Rather than merging PDFs, build a single page with all slides stacked (using the static HTML approach below) and print that to PDF once. Use CSS `@media print` with `page-break-after: always` between slides.

### Format: HTML (vector, self-contained)

For each slide:
1. Wait for slide to finish rendering.
2. Extract `document.getElementById('slide-root').innerHTML` via `page.evaluate()`.
3. Also extract any inline styles applied by layout mutations.

Bundle all slides into a single self-contained HTML file:
- All slide DOMs as hidden `<div class="slide">` elements.
- All CSS (theme.css content) inlined in a `<style>` tag.
- Font files as base64-encoded data URLs in `@font-face` rules.
- KaTeX CSS inlined (for math rendering that already happened — the rendered math is in the DOM as HTML/SVG).
- A minimal ~20 line JS navigator: shows one slide at a time, arrow keys to flip, slide counter.
- No external dependencies. One file. Works offline.

### Format: PNG (raster)

For each slide:
1. Wait for slide to finish rendering.
2. Call `page.screenshot({path: "slide-NNN.png"})`.
3. Save to the output directory.

### Dependency

Same as `record` — `auditorium[record]` (Playwright). The `export` command checks for it at runtime.

---

## Implementation order

1. **Docstring change** — remove docstring rendering from `_run_slide`, update `demo_deck.py` to use `md()` for all content. This is the breaking change. Ship as v3.0.
2. **`auditorium export`** — build on existing recorder infrastructure. Can ship in v3.0 alongside the docstring change.
3. **Presenter mode** — add `/presenter` endpoint, `notes`/`next_preview` messages, presenter HTML. Can ship in v3.0 or v3.1.

## What's NOT in scope

- Live collaboration (multiple people controlling the same deck)
- Slide thumbnails sidebar
- Custom themes beyond the shipped academic-serif
- Audio narration in recordings or exports
- Animated GIF export (use ffmpeg on the webm)
