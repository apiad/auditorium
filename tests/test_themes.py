import re
from pathlib import Path

THEMES = Path(__file__).parent.parent / "auditorium" / "themes"
STATIC = Path(__file__).parent.parent / "auditorium" / "static"

# A bare `transition:` declaration, not the `--aud-transition:` custom property.
BARE_TRANSITION = re.compile(r"(?<!-)\btransition\s*:", re.MULTILINE)


def css_files():
    return sorted(THEMES.glob("*.css")) + sorted(STATIC.glob("*.css"))


def test_no_shipped_css_uses_a_bare_transition_property():
    """CSSTransitions vanish from getAnimations() the instant they finish.

    After that, a backward seek past them silently no-ops and the element
    strands at its end value. Persistent keyframes (fill: both) seek back
    exactly, so shipped CSS must use animations, never transitions.
    """
    offenders = []
    for path in css_files():
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if BARE_TRANSITION.search(line):
                offenders.append(f"{path.name}:{i}: {line.strip()}")
    assert offenders == [], "bare transition: found in shipped CSS:\n" + "\n".join(offenders)


def test_the_custom_property_is_not_mistaken_for_a_transition():
    """Guard the regex itself: --aud-transition: is a custom property, not a rule."""
    assert BARE_TRANSITION.search("--aud-transition: aud-fade;") is None
    assert BARE_TRANSITION.search("  transition: opacity 0.3s;") is not None
