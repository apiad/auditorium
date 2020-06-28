# coding: utf8

import os


def path(p: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), p)


def fix_indent(content: str, tab_size: int = 0) -> str:
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

def fix_latex(content: str):
    def fix_ampersand(content: str):
        idx = content.find('&')
        no_scape_amp = lambda : True if idx==0 else content[idx-1]!='\\'
        while idx!=-1:
            if content.find('&amp;', idx, idx+6)==-1 and no_scape_amp():
                content=content[:idx]+' &amp; '+content[idx+1:]
            idx = content.find('&', idx+2)
        return content

    scape_char = {
        '&': fix_ampersand,
        '<': lambda x: x.replace('<',' &lt; '),
        '>': lambda x: x.replace('<',' &gt; '),
    }
    for fix in scape_char.values():
        content = fix(content)
    return content
