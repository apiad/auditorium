# coding: utf8


def fix_indent(content, tab_size=0):
    lines = content.split("\n")
    min_indent = 1e50

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

    lines = [" " * tab_size + l[min_indent:] for l in lines]

    while lines and not lines[0] or lines[0].isspace():
        lines.pop(0)

    return "\n".join(lines)
