import os
import re
import sys
from typing import Union

import click

# Regex to match file:line(func) or truncated file:line(func..
# Group 1: file, Group 2: line, Group 3: func
FUNC_RE = re.compile(r"^(.+):(-?\d+)\((.*?)(\)?)$")


def enabled() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    # Use click.isatty for more robust detection if possible, or stay with sys.stdout.isatty
    return sys.stdout.isatty()


def style(v: str, **kwargs) -> str:
    return click.style(v, **kwargs) if enabled() else v


def pct(v: str) -> str:
    return style(v, fg="yellow")


def time(v: Union[int, str, float]) -> str:
    res = str(v)
    if enabled():
        try:
            if isinstance(v, str) and v.replace(".", "", 1).lstrip("-").isdigit():
                v = float(v)
            if isinstance(v, (int, float)):
                # Use locale-aware formatting with 'n' specifier
                res = f"{v:n}"
        except Exception:
            pass
    return style(res, fg="magenta")


def func(v: str) -> str:
    if not enabled():
        return v
    m = FUNC_RE.match(v)
    if m:
        f, l, n, p = m.groups()
        # file: gray, line: white, func: bold cyan
        # p contains the optional closing parenthesis if it existed
        return f"{style(f, fg='bright_black')}:{l}({style(n, fg='cyan', bold=True)}{p}"
    return style(v, fg="cyan")


def loc(v: str) -> str:
    return style(v, fg="bright_black")
