---
type: design_doc
date: 2026-08-27
title: "Themed maths and geometry"
status: implemented
tags: [auditorium, themes, katex, svg, geometry, palette]
---

# Themed maths and geometry

## Overview

Auditorium 4.0 ships a geometry layer and bundles KaTeX, and neither is themed.
A theme's personality reaches its headings, its rules and its code blocks, and
then stops: every curve, arrow and axis on every theme renders in one
undifferentiated foreground colour, because `nodes.py` defaults each shape's
stroke to `currentColor`.

This was measured rather than assumed. The same figure — axis, target curve,
partial sum, marker, arrow, display formula, inline formula — was rendered on
`minimalist+dark`, `terminal+neon` and `academic+solarized`:

- **KaTeX is legible on all three.** It inherits colour, so there is no contrast
  bug to fix. An earlier draft of this document predicted one; the render
  disproved it.
- **`terminal+neon` styles its title with a cyan glow, a `$` prompt and a block
  cursor, and leaves the formula and all five shapes anonymous off-white.**
- **All geometry is one colour on every theme.** Axis, target and approximation
  are indistinguishable, which is precisely the distinction a mathematical
  figure exists to draw.

The target audience for 4.0 is people making algorithm and mathematics videos.
For them a figure without an ordered palette is not a stylistic shortfall, it is
a missing feature.

## Components

### The palette contract

Themes already separate structure from palette: `static/theme.css` carries
structure and default variable values, and the colour-axis themes override the
variables. Geometry follows that split exactly rather than introducing a second
mechanism.

`static/theme.css` grows defaults; each colour theme overrides them:

```css
--aud-geom-1 … --aud-geom-4   /* ordered categorical series */
--aud-geom-muted              /* axes, grid, reference marks */
--aud-geom-width              /* default stroke width */
```

Four series is a deliberate cap. A figure that needs a fifth simultaneous colour
is past the point where colour is doing the explaining.

### Node colouring

`nodes.py` stops defaulting to `currentColor` and defaults into the palette:

```python
Path(d, series=2)        # var(--aud-geom-2)
Line(from_, to, muted=True)   # var(--aud-geom-muted)
Arrow(from_, to, stroke="#f00")  # explicit override, unchanged
```

Resolution happens in Python and produces a CSS string. That is not layout
computation — D6 forbids Python resolving *anchors*, not composing a colour.

### Applying stroke in the engine

No change. An earlier draft of this document claimed `var()` cannot resolve
inside an SVG presentation attribute and that the engine would have to switch to
`el.style`. **That is wrong, and the test written to catch it disproved it
instead**: SVG2 defines presentation attributes as CSS declarations at the
lowest specificity, so `stroke="var(--aud-geom-2)"` resolves exactly like a
style property. Verified in Chromium against a variable set to `rgb(1, 2, 3)`,
and confirmed non-vacuous by removing the engine's stroke assignment and
watching the test fail.

The engine keeps setting attributes. The browser test stays regardless, because
it is the only check that distinguishes "the attribute was set" from "the shape
is the colour the theme asked for".

### KaTeX

Structural rules only, in `static/theme.css`, because they are the same on every
theme: display maths currently inherits the body line-height and crowds its
neighbours, and inline maths sits fractionally off the text baseline. Colour is
already inherited and needs no rule.

## Decisions

### D1. Themes carry the palette; nodes name a role

A node names *which* series it belongs to, never a colour. `series=2` says "the
second thing in this figure", and the theme decides what that looks like.

**Rationale.** It is the same reason a chart library takes a series index rather
than a hex code: it keeps a figure legible when the theme changes, which is the
entire premise of a composable theme system. A deck authored on `light` and
presented on `dark` keeps its meaning.

### D2. Series are explicit, not auto-cycled

Rejected: assigning the Nth drawn shape the Nth colour automatically.

**Rationale.** Auto-cycling looks better in exactly one situation — a demo that
draws three curves and nothing else — and betrays the author immediately
afterwards. An axis drawn first silently consumes series 1, and inserting a
reference line renumbers every colour below it. Explicit indices are stable
under edits; magic that depends on draw order is not.

### D3. Geometry is not made layout-aware

Rejected: having geometry avoid or reserve space against flowing text.

**Rationale.** In the probe, the curve runs through the formula because the
figure was placed at a y-coordinate where text happened to be. That is an
authoring mistake, not a theming gap. Making the SVG layer negotiate with DOM
layout is a large feature with its own design; conflating it with palette work
would sink both.

### D4. `currentColor` remains available

`stroke="currentColor"` still works for anyone who wants a shape to track the
text colour exactly. It stops being the *default*.

## Failure modes

**A theme that forgets the palette.** A colour theme shipping without
`--aud-geom-*` renders geometry in the `theme.css` defaults, which will look
wrong against its background rather than invisible. Mitigation: a test asserting
every colour-axis theme defines every palette variable — mechanical, and it
fails the day a new theme is added without them.

**Asserting on the attribute rather than the computed style.** A test reading
`getAttribute("stroke")` passes whenever the engine wrote *something*, including
a variable name that failed to resolve. Mitigation: the browser test asserts the
*computed* stroke against a known colour. This is what caught the false claim
above.

**Series drift.** An author renumbers a figure's series and the colours shuffle.
Accepted: that is the cost of explicitness, and it is visible immediately.

## Testing

**Palette lint** — every file in `themes/` whose header declares the colour axis
defines all six variables. Parses the existing `(color axis)` marker.

**Node serialization** — `series=` and `muted=` produce the right CSS strings,
and an explicit `stroke=` still wins.

**Computed stroke in a browser** — a node with `series=2` under a theme whose
`--aud-geom-2` is a known colour computes to that colour. Asserting on the
attribute instead would pass whenever the engine wrote anything at all.

**KaTeX spacing** — display maths has a margin distinct from a paragraph's.

## Delivery order

1. Palette defaults and KaTeX rules in `static/theme.css`; palette in each
   colour theme; the lint.
2. `series`/`muted` in `nodes.py`. The engine needed no change.
3. `examples/demo.py` rebuilt on top: Fourier partial sums and Newton's method.
