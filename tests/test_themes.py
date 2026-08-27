import re
from pathlib import Path

THEMES = Path(__file__).parent.parent / "auditorium" / "themes"
STATIC = Path(__file__).parent.parent / "auditorium" / "static"

# A bare `transition:` declaration, not the `--aud-transition:` custom property.
BARE_TRANSITION = re.compile(r"(?<!-)\btransition\s*:", re.MULTILINE)

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_comments(text: str) -> str:
    """Blank out CSS comments, preserving line structure so line numbers stay true.

    Without this the rule punishes its own documentation: the comment
    explaining *why* transitions are banned contains the word "transition"
    followed by a colon, and trips the check it is describing.
    """
    return _COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


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
        for i, line in enumerate(strip_comments(path.read_text()).splitlines(), 1):
            if BARE_TRANSITION.search(line):
                offenders.append(f"{path.name}:{i}: {line.strip()}")
    assert offenders == [], "bare transition: found in shipped CSS:\n" + "\n".join(offenders)


def test_the_custom_property_is_not_mistaken_for_a_transition():
    """Guard the regex itself: --aud-transition: is a custom property, not a rule."""
    assert BARE_TRANSITION.search("--aud-transition: aud-fade;") is None
    assert BARE_TRANSITION.search("  transition: opacity 0.3s;") is not None


def test_comments_are_not_scanned_but_real_rules_still_are():
    """The rule must not fire on prose, and must still fire on a declaration.

    Both halves matter: stripping comments is only safe if it does not also
    blind the check to the thing it exists to catch.
    """
    css = "/* not a transition: a keyframe */\n.x { transition: opacity 1s; }\n"
    stripped = strip_comments(css)
    assert BARE_TRANSITION.search(stripped.splitlines()[0]) is None
    assert BARE_TRANSITION.search(stripped.splitlines()[1]) is not None
    assert len(stripped.splitlines()) == len(css.splitlines())
