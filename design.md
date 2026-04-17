---
type: design_doc
date: 2026-04-17
title: Auditorium 2.0 rewrite
status: draft
suggested_location: Efforts/Projects/auditorium/Architecture.md
tags: [auditorium, slides, python, presentations, async, fastapi, websockets, rewrite]
---

# Auditorium 2.0: Python-scripted live slide framework rewrite

## Overview

Auditorium 2.0 is a ground-up rewrite of the auditorium Python slide framework, preserving its original thesis — that live technical presentations are best authored as imperative Python scripts, not declarative markdown documents — while replacing the entire implementation. The 1.x codebase is built on reveal.js with a custom websocket bridge; 2.0 drops reveal.js, drops the bridge, and rebuilds on a minimal FastAPI server, a hand-written HTML shell styled with Tailwind via CDN, and a small, deliberate async vocabulary for driving slides from Python.

Each slide is an `async def` function in a `deck.py` file, decorated with `@deck.slide`. The function's docstring renders as markdown at slide entry; its body is imperative Python that orchestrates DOM mutations, timed animations, and keypress-gated reveals through awaitable primitives (`show`, `hide`, `sleep`, `step`, `columns`, `rows`, `place`, `stable_top`, `md`, `show_md`). The FastAPI server holds authoritative slide state and pushes DOM mutations over websocket to the client. The client is dumb: it receives mutations and applies them. Flexbox handles layout; CSS transitions handle motion; Python drives state.

The primary deliverable is a live presentation — the presenter runs `python deck.py`, a browser opens, and the talk proceeds under keypress control. Video recording is a v2.1 feature, implemented by driving the same engine through a headless browser and capturing frames after each mutation acknowledgment. Static HTML bundles are not supported and not planned; talks are shared as git repos plus run instructions, or eventually as recorded videos.

The target audience is technical presenters — researchers, lecturers, engineers — who want arbitrary Python integration (live-computed plots, numerical demos, programmatic slide generation) and are willing to trade shareable static artifacts for scripting flexibility. The 1.x user base is dormant, which licenses an aggressive rewrite without migration guides or parallel version maintenance. The brand, the PyPI namespace, and the GitHub project carry forward; the code does not.

## Components

### The Deck object

The top-level object the user instantiates. Holds metadata (title, theme name, extra CSS), the ordered list of registered slides, and the server lifecycle. Exposes `deck.slide` as a decorator for registering async slide functions and `deck.run()` to start the server and begin presentation. One `Deck` per `deck.py` by convention; the filename is not enforced, and multiple decks in one project is supported via separate files.

### Slide functions

Async functions decorated with `@deck.slide`, optionally parameterized with `order=N` and `title=...`. Each receives a slide context object as its first parameter, exposing the async vocabulary. The docstring is parsed as markdown and rendered at slide entry before the body executes. The body may call the async vocabulary, run arbitrary Python, gather parallel operations via `asyncio.gather`, and loop freely. Slide execution ends when the function returns (advancing to the next slide) or when the presenter presses forward-to-next-slide during an awaited `step`.

### The async vocabulary

The slide context exposes the v1 primitive operations:

- Content: `show(element)`, `hide(selector)`, `replace(selector, element)`, `set_class(selector, cls)`, `remove_class(selector, cls)`
- Timing: `sleep(seconds)`, `step()` (waits for keypress)
- Markdown: `md(string)` for inline rendering, `show_md(path)` to load an external file
- Layout: `columns(sizing)`, `rows(sizing)`, `place(element, x, y)`, `stable_top()`

DOM-mutating methods are awaitable because each round-trips through the server to the client for acknowledgment. Region scoping (entering/exiting a `with` block on a layout region) is synchronous because it manipulates only a server-local Python target stack.

### The server

A FastAPI application that serves the HTML shell, exposes a websocket endpoint for the client mutation channel, and runs slide functions as long-lived async tasks. Holds the authoritative current-slide index, current step, and the ordered list of mutations applied. Translates keypress events from the client into coroutine continuations or slide transitions. uvicorn is the intended runner; FastAPI + uvicorn are the only required runtime dependencies beyond the standard library and a markdown parser.

### The HTML shell

A single static HTML page served at the root. Contains a full-viewport container div as the slide root, Tailwind CSS loaded via CDN, KaTeX via CDN for math, a syntax-highlighting library via CDN for code, a Google Fonts academic-serif pair, and a small client-side JavaScript module that handles the websocket connection, applies mutations, captures keypress events, and acknowledges each mutation back to the server. No framework, no bundler, no build step.

### The layout system

All layout is flexbox by default. The slide container is a flex-column with centered alignment on both axes. New elements append and push existing content to maintain centering — content displaces as more content arrives. Four primitives provide structured layouts:

- `columns(sizing)` creates a horizontal flex container with N sub-regions. `sizing` is either an integer (equal widths) or a list of ratios (`[2, 1]` produces a 2/3 + 1/3 split).
- `rows(sizing)` is the vertical equivalent.
- `place(element, x, y)` absolutely positions an element at pixel coordinates, serving as the escape hatch when flex is wrong.
- `stable_top()` is a top-aligned region where new content pushes downward rather than displacing centered content upward — for progressive text reveals where reading position should remain stable.

Regions are created asynchronously (a server round-trip instantiates DOM nodes) and scoped synchronously via `with region:` blocks that push and pop the current insertion target on a Python-side stack. Nesting is supported (a `columns` inside a `rows` inside a `stable_top` is valid).

### The theme

v1 ships one theme, academic-serif, expressed as a set of default Tailwind utility classes applied to the shell container, a Google Fonts pairing (a serif display face with a mathematically compatible body face), and a small shipped stylesheet for slide-level defaults. Theme customization is a CSS-level concern: users provide an override stylesheet via `Deck(extra_css=...)` or edit the shell directly in advanced cases.

### Navigation

Forward-within-slide on right arrow or space: advances the next awaited `step()` or, if none pending, advances to the next slide. Forward-to-next-slide on page-down: advances unconditionally, skipping remaining awaited steps. Back on left arrow: moves to the start of the previous slide. Restart current slide on `r`. Numeric slide jump on digits followed by enter. Backward navigation within a slide is deliberately unsupported.

## Decisions

### D1. Ground-up rewrite, not a refactor

**Context.** 1.x is built on reveal.js with a custom websocket bridge and carries years of architectural assumptions. The v2 design shares none of those assumptions: no reveal.js, no Jinja templates, no slide-as-class model, different DOM protocol, different layout system.

**Decision.** 2.0 is a ground-up rewrite on a fresh codebase. No incremental migration of 1.x code.

**Rationale.** The two architectures share thesis but not implementation. Incremental refactoring would mean fighting 1.x assumptions while carrying reveal.js along indefinitely. A clean rewrite is faster to build, easier to reason about, and honest about what the project has become.

### D2. Retain the auditorium brand; tag 1.x as legacy

**Context.** The auditorium project has brand equity on GitHub and PyPI but zero active users. Options included launching under a new name, maintaining parallel 1.x and 2.x branches, or pushing 2.0 to main with minimal ceremony.

**Decision.** Tag the current main as `v1-legacy` for permanent retrievability, then develop 2.0 directly on main. Publish 2.0.0 to PyPI under the existing `auditorium` namespace. Rewrite the README completely before release. Leave 1.x PyPI releases published with a deprecation note.

**Rationale.** With no active users, parallel branch maintenance is pure ceremony. Brand equity (search ranking, stars, historical links) carries forward for free. The `v1-legacy` tag preserves the old implementation without cluttering active development. A README rewrite turns the repo's first impression from "abandoned since 2019" into "active project with history."

### D3. Server-driven imperative Python

**Context.** Three architectures were considered: a markdown-first static compiler emitting a self-contained HTML bundle, a Pyodide-based client-side isomorphic app, and a server-driven imperative scripting engine.

**Decision.** Server-driven imperative Python. FastAPI server, websocket DOM channel, minimal HTML client.

**Rationale.** The other models optimize for shareable static output (compiler) or single-user interactivity (Pyodide). Neither fits the target use case: live technical presentations where arbitrary Python integration, async orchestration, and video-recordability matter more than static shareability. The imperative model matches the mental model of directing a presentation.

### D4. No violetear dependency

**Context.** Earlier design iterations included violetear as a framework dependency for its atomic CSS engine, HTML builder, and Pyodide bridge.

**Decision.** Drop violetear. Use FastAPI directly for the server, Tailwind via CDN for CSS, and plain HTML string construction for elements.

**Rationale.** Violetear's primary value was the isomorphic/Pyodide layer and the atomic CSS engine. Neither is needed in a server-driven architecture. Tailwind from CDN is simpler than a Python-generated atomic engine, and Pyodide is not part of the design. Removing violetear reduces dependency surface.

### D5. Slide = async function with markdown docstring

**Context.** Authoring surface options ranged from external `.md` files with front-matter to pure Python classes. Auditorium 1.x supported markdown via docstring, which users found natural.

**Decision.** Each slide is an `async def` function decorated with `@deck.slide`. The docstring renders as markdown at slide entry; the body is imperative Python. External `.md` files load via `await show_md(path)` for long content.

**Rationale.** FastAPI's decorator pattern is the proven ergonomic default for "list of handlers with minimal ceremony." Docstrings keep prose and scripting physically adjacent. Pure-text slides are one docstring with an empty body; scripted slides have proportional code. Preserving the docstring pattern honors what worked in 1.x.

### D6. Both timing models available per-moment

**Context.** Timing could be purely clock-driven (`sleep`), purely keypress-driven (`step`), or both.

**Decision.** Both are first-class and mixable within a single slide.

**Rationale.** Real talks use both — keypress-gated reveals for rhetorical beats, timed animations for continuous content. Async/await makes mixing natural.

### D7. Backward navigation: previous slide, not previous step

**Context.** Imperative async scripts have no natural undo. Options were re-run-and-fast-forward, undo log, or disallow step-level back.

**Decision.** Left arrow navigates to the start of the previous slide. Restarting the current slide is bound to `r`. Step-level back is not supported.

**Rationale.** Keynote and PowerPoint "back" returns to the previous slide — audience expectations match. Implementing step-level back is expensive for a feature rarely needed. If a presenter needs to re-show a step, restarting the slide is a two-keypress path.

### D8. Flexbox-first layout with four primitives

**Context.** Layout could be absolute-positioning, grid-based, or flow-based.

**Decision.** Flexbox-first. Default container is a centered flex column. Four v1 primitives: `columns`, `rows`, `place`, `stable_top`.

**Rationale.** Flexbox matches progressive content entry. CSS transitions on flex properties produce Keynote-quality motion without Python-side animation logic. Absolute positioning exists as an escape hatch. `stable_top` addresses the one predictable failure mode of flow layouts — text reflow during progressive reveals.

### D9. Column/row sizing: positional ratios

**Context.** Sizing could be positional, keyword, or both.

**Decision.** Positional only: `columns(3)` for equal, `columns([2, 1])` for ratios.

**Rationale.** Matches Streamlit convention familiar to the target audience. Keeps common case ceremony-free. Named regions can be added later without breaking positional.

### D10. Tailwind via CDN, one academic-serif theme, no build step

**Context.** CSS options included a Python-generated atomic engine, bundled Tailwind, Tailwind via CDN, or handwritten CSS.

**Decision.** Tailwind via CDN for utility classes, plus a small shipped theme stylesheet. KaTeX and syntax highlighter also via CDN. No build step.

**Rationale.** CDN produces a working UI with zero configuration. Bundling would require a compiler in the install path, contradicting the "just run `python deck.py`" simplicity goal. The academic-serif theme carries visual identity; Tailwind provides per-slide overrides.

### D11. Slide order: registration order with explicit override

**Context.** Ordering options: registration, explicit parameter, filesystem, constructor list.

**Decision.** Registration order by default; `@deck.slide(order=N)` overrides. Explicit orders resolve first; remaining slides fill by registration.

**Rationale.** Registration order matches reading order and requires no ceremony. Explicit override handles iteration-time reordering without moving code blocks.

### D12. Video recording deferred to 2.1

**Context.** Video recording is tractable given the server-driven architecture — drive a headless browser through the talk and capture frames.

**Decision.** Not in 2.0. 2.1 adds a `deck record` CLI command that uses Playwright to drive the deck and produce an mp4.

**Rationale.** Live presentation is the primary deliverable. Recording is a secondary mode addable without changing any 2.0 primitives. Deferring keeps 2.0 scope tight.

## Open questions

External `.md` file path resolution. `show_md(path)` is specified but resolution convention (relative to `deck.py`, relative to a `content/` folder, absolute) and whether embedded markdown may reference Python helpers is undecided. Defer until the first real need.

Keyboard binding customization. v2.0 hardcodes navigation keys. A `Deck(keybindings=...)` override is the natural extension point if demanded.

Multi-window presenter view. A speaker-view window showing notes, timer, and next-slide preview. Implementable as a second websocket client with a different rendering template. Defer to 2.2.

State recovery on browser reload. Simplest: restart the current slide on reconnect. More complex: maintain a mutation log and replay. Start simple; revisit if users reload mid-talk often.

Animation discipline enforcement. The architecture permits authors to animate DOM properties over time from Python via looped calls. This produces janky websocket-throttled motion. Whether to actively discourage this in the vocabulary (by omitting fine-grained primitives) or document it as an anti-pattern: default to documentation.

## Next steps

1. Tag current `main` on the auditorium repo as `v1-legacy` and push the tag.
2. Clear `main` or create an orphan commit on it to begin the 2.0 scaffold. (Branch hygiene is low-priority given no active users.)
3. Scaffold the new project with FastAPI and uvicorn as the only required runtime dependencies. Target Python 3.12+.
4. Build the HTML shell: Tailwind via CDN, KaTeX, syntax highlighter, Google Fonts academic-serif pair, client-side JS for websocket and keypress.
5. Define the websocket message protocol: mutation types, region creation, target-stack push/pop, keypress events, mutation acknowledgments.
6. Implement the `Deck` object with `@slide` decorator, `order` parameter, and `run()` method.
7. Implement the slide context object with the v1 vocabulary.
8. Implement the layout primitives and validate region target-stack behavior under nesting.
9. Wire up docstring extraction: on slide entry, parse the function's docstring as markdown and emit as initial content.
10. Implement navigation: forward-within, forward-to-next, back-to-previous, restart, numeric jump.
11. Build the academic-serif theme: Google Fonts pair, base Tailwind classes, CSS transitions on flex properties.
12. Author one substantive example deck (a 10–15 slide technical talk) to pressure-test the vocabulary. This is the dogfooding gate.
13. Publish pre-releases (`2.0.0a1`, `b1`, `rc1`) on PyPI as the vocabulary stabilizes.
14. Rewrite the README completely — new positioning, code examples, demo gif.
15. Publish 2.0.0 on PyPI. Add a deprecation note to 1.x release descriptions.
16. Optionally: a single announcement post cashing in brand equity.

## Failure modes

**Reflow during text reveals.** Progressive reveals in a centered-flex container shift earlier content. Mitigation: `stable_top` as a first-class primitive and a documented pattern for prose-heavy slides.

**Websocket latency perceived as lag.** Local round-trips are under 10ms, but remote presentation could feel laggy. Mitigation: the target use case is presenter-local. If remote becomes a priority, move more state to the client.

**Python-side animation temptation.** Authors may loop fine-grained DOM updates, producing janky websocket-throttled motion. Mitigation: documented discipline that Python emits state transitions while CSS handles motion. The v1 vocabulary omits fine-grained primitives to reinforce this.

**Half-migrated repo state.** Having the README still reflect 1.x while main contains 2.0 work-in-progress signals confusion to new visitors and abandonment to returning ones. Mitigation: either finish the README rewrite before merging 2.0 to main, or gate 2.0 work on a `v2-dev` branch until the README is ready. Do not let main float in a mixed state.

**Re-attracting users before 2.0 is solid.** Early brand-equity cash-in (announcement posts, social media) before the implementation has stabilized risks a second round of disillusionment. Mitigation: announce only after the dogfooded example deck exists and the API has survived authoring a real talk.

## Glossary

**Deck.** The top-level object holding the ordered slides and server lifecycle. One per `deck.py` by convention.

**Slide.** An async function decorated with `@deck.slide`. Docstring renders as markdown; body is imperative Python.

**Slide context.** The parameter passed to each slide function, exposing the async vocabulary.

**Step.** A keypress-gated pause in slide execution, awaited via `await step()`.

**Region.** A DOM container created by a layout primitive (`columns`, `rows`, `stable_top`) and scoped by a `with` block. Serves as the insertion target for subsequent `show()` calls.

**Vocabulary.** The set of async methods on the slide context: `show`, `hide`, `replace`, `set_class`, `remove_class`, `sleep`, `step`, `md`, `show_md`, `columns`, `rows`, `place`, `stable_top`.

**v1-legacy.** Git tag pointing at the final state of auditorium 1.x (reveal.js-based). Preserved for retrievability; no further development.
