# coding: utf8

import os


def path(p):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), p)


def fix_indent(content, tab_size=0):
    lines = content.split("\n")
    min_indent = 1000

    for l in lines:
        if not l or l.isspace():
            continue

        indent_size = 0

        for c in l:
            if c.isspace():
                indent_size += 1
            else:
                break

        min_indent = min(indent_size, min_indent)

    if min_indent < 10000:
        lines = [" " * tab_size + l[min_indent:] for l in lines]

    while lines and (not lines[0] or lines[0].isspace()):
        lines.pop(0)

    return "\n".join(lines)
