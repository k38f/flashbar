from __future__ import annotations

import shutil
import sys
from typing import IO, Optional

from .bar import RESET, _truncate_ansi, _visible_len, resolve_color

# Box-drawing characters for panel borders.
# Default uses rounded corners — easier on the eyes than square ones.
_BORDERS = {
    "rounded": {"tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "h": "─", "v": "│"},
    "square":  {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│"},
    "double":  {"tl": "╔", "tr": "╗", "bl": "╚", "br": "╝", "h": "═", "v": "║"},
    "heavy":   {"tl": "┏", "tr": "┓", "bl": "┗", "br": "┛", "h": "━", "v": "┃"},
    "ascii":   {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|"},
}


def _term_width(default: int = 80) -> int:
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return default


def _is_tty(file: IO[str]) -> bool:
    return bool(getattr(file, "isatty", lambda: False)())


# -- Panel ------------------------------------------------

def panel(
    text: str,
    title: Optional[str] = None,
    color: Optional[str] = None,
    width: Optional[int] = None,
    style: str = "rounded",
    padding: int = 1,
) -> str:
    """Wrap text in a bordered panel. Returns a string ready to print.

    Args:
        text:    Body content. May contain newlines.
        title:   Optional title shown in the top border.
        color:   Border color — name ('cyan') or hex ('#FF5733').
        width:   Total width including borders. None = auto-fit content.
        style:   Border style: rounded, square, double, heavy, ascii.
        padding: Spaces of horizontal padding inside the box.

    Usage:
        print(panel("Hello", title="Greeting", color="cyan"))
    """
    chars = _BORDERS.get(style, _BORDERS["rounded"])
    color_code = resolve_color(color) if color else ""
    reset = RESET if color_code else ""

    lines = text.split("\n")

    # Auto-size width to fit the longest content line + padding + borders
    if width is None:
        content_w = max((_visible_len(line) for line in lines), default=0)
        title_w = _visible_len(title) + 4 if title else 0
        width = max(content_w + padding * 2 + 2, title_w + 4, 10)
        # Don't exceed terminal width
        width = min(width, _term_width())

    inner_w = max(width - 2, 0)
    pad_str = " " * padding

    out = []

    # Top border with optional title
    if title:
        title_visible = f" {title} "
        # Fit title; truncate if too long
        if _visible_len(title_visible) > inner_w - 2:
            title_visible = title_visible[: max(0, inner_w - 2)]
        remain = inner_w - _visible_len(title_visible) - 1
        top = f"{chars['tl']}{chars['h']}{title_visible}{chars['h'] * max(remain, 0)}{chars['tr']}"
    else:
        top = f"{chars['tl']}{chars['h'] * inner_w}{chars['tr']}"
    out.append(f"{color_code}{top}{reset}")

    # Body lines — pad each to inner width, preserving any inline ANSI
    for line in lines:
        vlen = _visible_len(line)
        avail = inner_w - padding * 2
        if vlen > avail:
            line = _truncate_ansi(line, avail)
            vlen = _visible_len(line)
        space_after = " " * max(avail - vlen, 0)
        out.append(
            f"{color_code}{chars['v']}{reset}{pad_str}{line}{space_after}{pad_str}"
            f"{color_code}{chars['v']}{reset}"
        )

    # Bottom border
    bottom = f"{chars['bl']}{chars['h'] * inner_w}{chars['br']}"
    out.append(f"{color_code}{bottom}{reset}")

    return "\n".join(out)


# -- Status indicators ------------------------------------

# These return strings — the user calls print() themselves.
# Keeps the API consistent with panel() and rule().

def success(msg: str) -> str:
    """Green checkmark + message."""
    return f"{resolve_color('green')}✓{RESET} {msg}"


def error(msg: str) -> str:
    """Red X + message."""
    return f"{resolve_color('red')}✗{RESET} {msg}"


def warn(msg: str) -> str:
    """Yellow warning sign + message."""
    return f"{resolve_color('yellow')}⚠{RESET} {msg}"


def info(msg: str) -> str:
    """Cyan info sign + message."""
    return f"{resolve_color('cyan')}ℹ{RESET} {msg}"


# -- Rule (horizontal divider) -----------------------------

def rule(label: str = "", width: Optional[int] = None, color: Optional[str] = None) -> str:
    """Horizontal divider line. Optional centered label.

    Args:
        label: Text centered on the rule. Empty for plain line.
        width: Line width. None = full terminal width.
        color: Color — name or hex. Default is dim.
    """
    if width is None:
        width = _term_width()

    color_code = resolve_color(color) if color else "\033[2m"  # dim by default
    reset = RESET

    if label:
        label_w = _visible_len(label) + 2  # spaces around label
        if label_w >= width:
            return f"{color_code}{label}{reset}"
        side = (width - label_w) // 2
        right = width - label_w - side
        return f"{color_code}{'─' * side} {label} {'─' * right}{reset}"
    return f"{color_code}{'─' * width}{reset}"


# -- print helpers (optional convenience) ------------------

def print_panel(
    text: str,
    title: Optional[str] = None,
    color: Optional[str] = None,
    file: Optional[IO[str]] = None,
    **kwargs,
) -> None:
    """Convenience: build a panel and print it."""
    f = file or sys.stdout
    if _is_tty(f):
        f.write(panel(text, title=title, color=color, **kwargs) + "\n")
    else:
        # Strip styling for non-TTY: just print body with title prefix
        if title:
            f.write(f"[{title}] ")
        f.write(text + "\n")
    f.flush()
