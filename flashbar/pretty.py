from __future__ import annotations

import re
import shutil
import sys
from typing import IO, Optional

from .bar import RESET, _close_ansi, _truncate_ansi, _visible_len, resolve_color


_BORDERS = {
    "rounded": {"tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "h": "─", "v": "│"},
    "square": {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│"},
    "double": {"tl": "╔", "tr": "╗", "bl": "╚", "br": "╝", "h": "═", "v": "║"},
    "heavy": {"tl": "┏", "tr": "┓", "bl": "┗", "br": "┛", "h": "━", "v": "┃"},
    "ascii": {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|"},
}

_ANSI_RE = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x1b\x07]*(?:\x07|\x1b\\)|[@-_])"
)
_ASCII_FALLBACK = str.maketrans({
    "╭": "+", "╮": "+", "╰": "+", "╯": "+",
    "┌": "+", "┐": "+", "└": "+", "┘": "+",
    "╔": "+", "╗": "+", "╚": "+", "╝": "+",
    "┏": "+", "┓": "+", "┗": "+", "┛": "+",
    "─": "-", "═": "-", "━": "-",
    "│": "|", "║": "|", "┃": "|",
    "✓": "+", "✗": "x", "⚠": "!", "ℹ": "i",
})


def _term_width(default: int = 80) -> int:
    try:
        return max(shutil.get_terminal_size().columns, 1)
    except Exception:
        return default


def _is_tty(file: IO[str]) -> bool:
    try:
        return bool(getattr(file, "isatty", lambda: False)())
    except (OSError, TypeError, ValueError):
        return False


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text).replace("\x1b", "")


def _normalise_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _expand_tabs(text: str, start_column: int = 0) -> str:
    if "\t" not in text:
        return text

    result = []
    parts = text.split("\t")
    for index, part in enumerate(parts):
        result.append(part)
        if index == len(parts) - 1:
            break
        column = start_column + _visible_len("".join(result))
        result.append(" " * (8 - column % 8))
    return "".join(result)


def _plain_for_stream(file: IO[str]) -> bool:
    if not _is_tty(file):
        return True

    encoding = getattr(file, "encoding", None)
    if isinstance(encoding, str):
        try:
            "─✓✗⚠ℹ".encode(encoding)
        except (LookupError, UnicodeEncodeError):
            return True
    return False


def _text_for_stream(text: str, file: IO[str]) -> str:
    encoding = getattr(file, "encoding", None)
    if not isinstance(encoding, str):
        return text
    try:
        return text.encode(encoding).decode(encoding)
    except UnicodeEncodeError:
        return text.encode(encoding, errors="replace").decode(encoding)
    except LookupError:
        return text


def _plain_output(plain: Optional[bool]) -> bool:
    if plain is not None:
        return plain
    return _plain_for_stream(sys.stdout)


def _truncate(text: str, width: int) -> str:
    if _visible_len(text) <= width:
        return text

    result = _truncate_ansi(text, width)
    # Older versions of the shared helper always added RESET, even to plain text.
    if "\x1b" not in text and result.endswith(RESET):
        result = result[:-len(RESET)]
    return result


def _close_inline_style(text: str) -> str:
    return _close_ansi(text)


def _write_compatible(file: IO[str], text: str) -> None:
    encoding = getattr(file, "encoding", None)
    if isinstance(encoding, str):
        try:
            text.encode(encoding)
        except (LookupError, UnicodeEncodeError):
            text = text.translate(_ASCII_FALLBACK)
            try:
                text = text.encode(encoding, errors="replace").decode(encoding)
            except LookupError:
                text = text.encode("ascii", errors="replace").decode("ascii")

    try:
        file.write(text)
    except UnicodeEncodeError as exc:
        fallback_encoding = getattr(exc, "encoding", None) or encoding or "ascii"
        safe = text.translate(_ASCII_FALLBACK)
        try:
            safe = safe.encode(fallback_encoding, errors="replace").decode(
                fallback_encoding
            )
        except (LookupError, UnicodeError):
            safe = safe.encode("ascii", errors="replace").decode("ascii")
        file.write(safe)


# -- Panel ------------------------------------------------

def panel(
    text: str,
    title: Optional[str] = None,
    color: Optional[str] = None,
    width: Optional[int] = None,
    style: str = "rounded",
    padding: int = 1,
    plain: Optional[bool] = None,
) -> str:
    """Wrap text in a bordered panel and return it as a string.

    ``plain=True`` strips inline terminal styling and uses an ASCII border,
    which is useful for redirected output and legacy console encodings.
    """
    plain_output = _plain_output(plain)
    if not isinstance(padding, int) or isinstance(padding, bool):
        raise TypeError("padding must be an integer")
    if padding < 0:
        raise ValueError("padding must be >= 0")
    if width is not None:
        if not isinstance(width, int) or isinstance(width, bool):
            raise TypeError("width must be an integer or None")
        if width < padding * 2 + 2:
            raise ValueError("width is too small for the requested padding")
        if title and width < 3:
            raise ValueError("width is too small for a panel title")

    chars = (
        _BORDERS["ascii"]
        if plain_output
        else _BORDERS.get(style, _BORDERS["rounded"])
    )
    color_code = resolve_color(color) if color and not plain_output else ""
    border_reset = RESET if color_code else ""

    lines = _normalise_lines(str(text))
    clean_title = None if title is None else str(title).replace("\r", " ").replace("\n", " ")
    if plain_output:
        lines = [_strip_ansi(line) for line in lines]
        if clean_title is not None:
            clean_title = _strip_ansi(clean_title)
        if plain is None:
            lines = [_text_for_stream(line, sys.stdout) for line in lines]
            if clean_title is not None:
                clean_title = _text_for_stream(clean_title, sys.stdout)
    lines = [_expand_tabs(line, padding + 1) for line in lines]
    if clean_title is not None:
        clean_title = _expand_tabs(clean_title, 3)

    minimum_width = padding * 2 + 2
    if width is None:
        content_w = max((_visible_len(line) for line in lines), default=0)
        title_w = _visible_len(clean_title) + 4 if clean_title else 0
        wanted = max(content_w + padding * 2 + 2, title_w + 4, 10)
        width = max(min(wanted, _term_width()), minimum_width)

    inner_w = width - 2
    available = inner_w - padding * 2
    pad_str = " " * padding
    out = []

    if clean_title:
        title_text = f" {clean_title} "
        title_text = _truncate(title_text, max(inner_w - 2, 0))
        title_w = _visible_len(title_text)
        remain = inner_w - title_w - 1
        title_text = _close_inline_style(title_text)
        if color_code:
            title_text += color_code
        top = (
            f"{chars['tl']}{chars['h']}{title_text}"
            f"{chars['h'] * max(remain, 0)}{chars['tr']}"
        )
    else:
        top = f"{chars['tl']}{chars['h'] * inner_w}{chars['tr']}"
    out.append(f"{color_code}{top}{border_reset}")

    for line in lines:
        line = _truncate(line, available)
        line_w = _visible_len(line)
        line = _close_inline_style(line)
        space_after = " " * max(available - line_w, 0)
        out.append(
            f"{color_code}{chars['v']}{border_reset}{pad_str}{line}{space_after}{pad_str}"
            f"{color_code}{chars['v']}{border_reset}"
        )

    bottom = f"{chars['bl']}{chars['h'] * inner_w}{chars['br']}"
    out.append(f"{color_code}{bottom}{border_reset}")
    return "\n".join(out)


# -- Status indicators ------------------------------------

def _status(
    msg: str,
    symbol: str,
    fallback: str,
    color: str,
    plain: Optional[bool],
) -> str:
    text = str(msg)
    if _plain_output(plain):
        text = _strip_ansi(text)
        if plain is None:
            text = _text_for_stream(text, sys.stdout)
        return f"[{fallback}] {text}"

    text = _close_inline_style(text)
    return f"{resolve_color(color)}{symbol}{RESET} {text}"


def success(msg: str, *, plain: Optional[bool] = None) -> str:
    """Green checkmark and a message."""
    return _status(msg, "✓", "OK", "green", plain)


def error(msg: str, *, plain: Optional[bool] = None) -> str:
    """Red X and a message."""
    return _status(msg, "✗", "x", "red", plain)


def warn(msg: str, *, plain: Optional[bool] = None) -> str:
    """Yellow warning sign and a message."""
    return _status(msg, "⚠", "!", "yellow", plain)


def info(msg: str, *, plain: Optional[bool] = None) -> str:
    """Cyan information sign and a message."""
    return _status(msg, "ℹ", "i", "cyan", plain)


# -- Rule (horizontal divider) -----------------------------

def rule(
    label: str = "",
    width: Optional[int] = None,
    color: Optional[str] = None,
    plain: Optional[bool] = None,
) -> str:
    """Return a horizontal divider, optionally with a centered label."""
    if width is None:
        width = _term_width()
    elif not isinstance(width, int) or isinstance(width, bool):
        raise TypeError("width must be an integer or None")
    if width < 1:
        raise ValueError("width must be >= 1")

    label = str(label).replace("\r", " ").replace("\n", " ")
    plain_output = _plain_output(plain)
    line_char = "-" if plain_output else "─"
    color_code = "" if plain_output else (resolve_color(color) if color else "\033[2m")
    reset = RESET if color_code else ""
    if plain_output:
        label = _strip_ansi(label)
        if plain is None:
            label = _text_for_stream(label, sys.stdout)
    label = _expand_tabs(label)

    label_w = _visible_len(label)
    if label and label_w + 2 <= width:
        side = (width - label_w - 2) // 2
        right = width - label_w - 2 - side
        label = _close_inline_style(label)
        if color_code:
            label += color_code
        result = f"{line_char * side} {label} {line_char * right}"
    elif label:
        result = _close_inline_style(_truncate(label, width))
        missing = width - _visible_len(result)
        if missing > 0:
            if color_code:
                result += color_code
            result += line_char * missing
    else:
        result = line_char * width
    return f"{color_code}{result}{reset}"


# -- print helpers (optional convenience) ------------------

def print_panel(
    text: str,
    title: Optional[str] = None,
    color: Optional[str] = None,
    file: Optional[IO[str]] = None,
    **kwargs,
) -> None:
    """Build and print a panel, using clean text for non-TTY streams."""
    f = file if file is not None else sys.stdout
    is_tty = _is_tty(f)
    explicit_mode = kwargs.get("plain") is not None
    if not explicit_mode:
        kwargs["plain"] = _plain_for_stream(f)
    rendered = panel(text, title=title, color=color, **kwargs)

    if is_tty or explicit_mode:
        output = rendered + "\n"
    else:
        clean_text = "\n".join(_strip_ansi(line) for line in _normalise_lines(str(text)))
        if title:
            clean_title = _strip_ansi(str(title).replace("\r", " ").replace("\n", " "))
            output = f"[{clean_title}] {clean_text}\n"
        else:
            output = clean_text + "\n"

    _write_compatible(f, output)
    f.flush()
