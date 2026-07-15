from __future__ import annotations

import math
import re
import shutil
import sys
import time
import unicodedata
from typing import IO, Iterable, Iterator, Optional, TypeVar

# -- themes & colors --------------------------------------

THEMES = {
    "default": {"fill": "█", "empty": "░", "color": "\033[94m"},
    "green":   {"fill": "█", "empty": "░", "color": "\033[92m"},
    "red":     {"fill": "█", "empty": "░", "color": "\033[91m"},
    "minimal": {"fill": "─", "empty": " ", "color": "\033[97m"},
    "retro":   {"fill": "#", "empty": ".", "color": "\033[93m"},
    "slim":    {"fill": "━", "empty": "╺", "color": "\033[96m"},
    "dots":    {"fill": "●", "empty": "○", "color": "\033[95m"},
    "arrow":   {"fill": "▸", "empty": "▹", "color": "\033[94m"},
}

NAMED_COLORS = {
    "blue":    "\033[94m",
    "green":   "\033[92m",
    "red":     "\033[91m",
    "yellow":  "\033[93m",
    "cyan":    "\033[96m",
    "magenta": "\033[95m",
    "white":   "\033[97m",
}

RESET = "\033[0m"
DIM   = "\033[2m"

# Eighths of a full block — used for smooth sub-character rendering.
# Index = how many eighths are filled (0 = empty, 7 = almost full).
_PARTIALS = (" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉")

_ANSI_RE = re.compile(
    r"(?:"
    r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC, including hyperlinks
    r"|\x1b\[[0-?]*[ -/]*[@-~]"  # CSI
    r"|\x1b[@-_]"  # two-character escape
    r")"
)
_DEFAULT_WIDTH = 40
_MIN_REDRAW_INTERVAL = 1.0 / 30.0  # cap redraws at ~30 fps
_TAB_SIZE = 8


T = TypeVar("T")


def resolve_color(color: Optional[str]) -> str:
    """Turn a color name ('cyan') or hex ('#FF5733') into an ANSI escape."""
    if color is None:
        return NAMED_COLORS["blue"]
    if color in NAMED_COLORS:
        return NAMED_COLORS[color]
    if isinstance(color, str) and color.startswith("#") and len(color) == 7:
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            return f"\033[38;2;{r};{g};{b}m"
        except ValueError:
            pass
    return NAMED_COLORS["blue"]


def _format_time(seconds: float) -> str:
    """Pretty-print seconds. Sub-minute durations show fractional seconds."""
    if seconds < 0 or not math.isfinite(seconds):
        return "--:--"
    if seconds < 60:
        # short tasks now show meaningful values instead of always "00:00"
        return f"{seconds:4.1f}s"
    seconds_int = int(seconds)
    if seconds_int < 3600:
        return f"{seconds_int // 60:02d}:{seconds_int % 60:02d}"
    h = seconds_int // 3600
    m = (seconds_int % 3600) // 60
    s = seconds_int % 60
    return f"{h}:{m:02d}:{s:02d}"


def _is_variation_selector(char: str) -> bool:
    codepoint = ord(char)
    return 0xFE00 <= codepoint <= 0xFE0F or 0xE0100 <= codepoint <= 0xE01EF


def _is_emoji_modifier(char: str) -> bool:
    return 0x1F3FB <= ord(char) <= 0x1F3FF


def _is_regional_indicator(char: str) -> bool:
    return 0x1F1E6 <= ord(char) <= 0x1F1FF


def _is_cluster_extension(char: str) -> bool:
    codepoint = ord(char)
    category = unicodedata.category(char)
    return (
        category in {"Mn", "Me", "Cf"}
        or _is_variation_selector(char)
        or _is_emoji_modifier(char)
        or 0xE0020 <= codepoint <= 0xE007F
    )


def _char_width(char: str) -> int:
    if _is_cluster_extension(char):
        return 0
    category = unicodedata.category(char)
    if category.startswith("C"):
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1


def _display_unit(text: str, start: int, column: int) -> tuple[int, int]:
    """Return the end index and terminal-cell width of one display unit."""
    char = text[start]
    if char == "\t":
        return start + 1, _TAB_SIZE - (column % _TAB_SIZE)

    if _is_regional_indicator(char):
        end = start + 1
        if end < len(text) and _is_regional_indicator(text[end]):
            end += 1
        return end, 2

    end = start + 1
    widths = [_char_width(char)]
    has_joiner = False
    emoji_presentation = False

    while end < len(text):
        next_char = text[end]
        if next_char == "\x1b":
            break
        if next_char == "\u200d":
            if end + 1 >= len(text) or text[end + 1] == "\x1b":
                end += 1
                break
            has_joiner = True
            end += 1
            widths.append(_char_width(text[end]))
            end += 1
            continue
        if not _is_cluster_extension(next_char):
            break
        if next_char == "\ufe0f" or next_char == "\u20e3":
            emoji_presentation = True
        end += 1

    if has_joiner and any(width == 2 for width in widths):
        return end, 2
    width = sum(widths)
    if emoji_presentation:
        width = max(width, 2)
    return end, width


def _visible_len(text: str) -> int:
    """Return terminal cells occupied by text, excluding ANSI controls."""
    column = 0
    i = 0
    while i < len(text):
        match = _ANSI_RE.match(text, i)
        if match:
            i = match.end()
            continue
        i, width = _display_unit(text, i, column)
        column += width
    return column


def _sgr_active(current: bool, escape: str) -> bool:
    if not (escape.startswith("\x1b[") and escape.endswith("m")):
        return current
    params = escape[2:-1].split(";")
    for param in params:
        current = False if param in {"", "0"} else True
    return current


def _osc8_active(current: bool, escape: str) -> bool:
    if not escape.startswith("\x1b]8;"):
        return current
    content = escape[2:]
    if content.endswith("\x07"):
        content = content[:-1]
    elif content.endswith("\x1b\\"):
        content = content[:-2]
    parts = content.split(";", 2)
    return bool(parts[2]) if len(parts) == 3 else current


def _close_ansi(text: str) -> str:
    """Close terminal styles and hyperlinks left open by user text."""
    sgr_active = False
    hyperlink_active = False
    for match in _ANSI_RE.finditer(text):
        escape = match.group()
        sgr_active = _sgr_active(sgr_active, escape)
        hyperlink_active = _osc8_active(hyperlink_active, escape)

    if hyperlink_active:
        text += "\x1b]8;;\x1b\\"
    if sgr_active:
        text += RESET
    return text


def _truncate_ansi(line: str, max_visible: int) -> str:
    """Truncate a line to a terminal-cell width without breaking ANSI codes."""
    if max_visible <= 0:
        return ""

    out = []
    column = 0
    i = 0
    sgr_active = False
    hyperlink_active = False
    truncated = False

    while i < len(line):
        match = _ANSI_RE.match(line, i)
        if match:
            escape = match.group()
            out.append(escape)
            sgr_active = _sgr_active(sgr_active, escape)
            hyperlink_active = _osc8_active(hyperlink_active, escape)
            i = match.end()
            continue

        end, width = _display_unit(line, i, column)
        if column + width > max_visible:
            truncated = True
            break
        out.append(line[i:end])
        column += width
        i = end

    if truncated and hyperlink_active:
        out.append("\x1b]8;;\x1b\\")
    if truncated and sgr_active:
        out.append(RESET)
    return "".join(out)


def _write_text(file: IO[str], text: str) -> None:
    """Write text after replacing glyphs unsupported by a legacy stream."""
    encoding = getattr(file, "encoding", None)
    if encoding:
        try:
            text = text.encode(encoding).decode(encoding)
        except (LookupError, UnicodeEncodeError):
            try:
                text = text.encode(encoding, errors="replace").decode(encoding)
            except LookupError:
                pass
    try:
        file.write(text)
    except UnicodeEncodeError as error:
        safe = text.encode(error.encoding, errors="replace").decode(error.encoding)
        file.write(safe)


def _stream_is_tty(file: IO[str]) -> bool:
    try:
        return bool(getattr(file, "isatty", lambda: False)())
    except (OSError, TypeError, ValueError):
        return False


# ---------------------------------------------------------

class Bar:
    """Terminal progress bar with ETA, speed, and themes.

    Args:
        total:      Number of steps to complete.
        width:      Bar width in characters (default 40).
        theme:      Built-in theme name. See THEMES dict.
        label:      Text shown before the bar.
        color:      Override color — name ('cyan') or hex ('#FF5733').
        fill:       Override fill character.
        empty:      Override empty character.
        show_eta:   Show estimated time remaining. Default True.
        show_speed: Show items/sec. Default False.
        smooth:     Use sub-character rendering for smoother bars.
                    None (default) = auto-enable for full-block fill ('█').
        file:       Output stream. Default sys.stderr.

    Usage:
        bar = Bar(100, label="Downloading")
        for i in range(100):
            bar.update()
    """

    def __init__(
        self,
        total: int,
        width: int = _DEFAULT_WIDTH,
        theme: str = "default",
        label: str = "",
        color: Optional[str] = None,
        fill: Optional[str] = None,
        empty: Optional[str] = None,
        show_eta: bool = True,
        show_speed: bool = False,
        smooth: Optional[bool] = None,
        file: Optional[IO[str]] = None,
    ) -> None:
        if isinstance(total, bool) or not isinstance(total, int):
            raise TypeError("total must be an integer")
        if total <= 0:
            raise ValueError("total must be > 0")
        if isinstance(width, bool) or not isinstance(width, int):
            raise TypeError("width must be an integer")
        if width <= 0:
            raise ValueError("width must be > 0")

        self.total = total
        self.width = width
        self.label = str(label).replace("\r", " ").replace("\n", " ")
        self.current = 0
        self.show_eta = show_eta
        self.show_speed = show_speed
        self.file = file if file is not None else sys.stderr

        # Disable colors/animation when output isn't a real terminal —
        # avoids spamming escape codes into log files and CI output.
        self._is_tty = _stream_is_tty(self.file)

        # Cache terminal width so we don't syscall on every redraw.
        self._term_w = self._query_term_width()

        # Construction is the only point available before the first manual step.
        self._start_time = time.monotonic()
        self._finished = False
        self._last_draw = float("-inf")
        self._line_open = False

        base = THEMES.get(theme, THEMES["default"])
        self.color = resolve_color(color) if color else base["color"]
        self.fill = fill if fill is not None else base["fill"]
        self.empty = empty if empty is not None else base["empty"]
        if _visible_len(self.fill) != 1:
            raise ValueError("fill must occupy exactly one terminal cell")
        if _visible_len(self.empty) != 1:
            raise ValueError("empty must occupy exactly one terminal cell")

        # Auto-enable smooth rendering when the fill is a full block.
        if smooth is None:
            smooth = (self.fill == "█")
        self.smooth = smooth

    # -- public api ----------------------------------------

    def update(self, step: int = 1) -> None:
        """Advance by `step` and redraw."""
        if isinstance(step, bool) or not isinstance(step, int):
            raise TypeError("step must be an integer")
        if step < 0:
            raise ValueError("step must be >= 0")
        if self._finished:
            return

        self.current = min(self.current + step, self.total)
        self._maybe_draw()

        if self.current >= self.total:
            self._finished = True

    def set(self, value: int) -> None:
        """Jump to a specific value and redraw."""
        new_value = max(0, min(int(value), self.total))
        if self._finished and new_value >= self.total:
            return
        if self._finished:
            self._start_time = time.monotonic()
        self.current = new_value
        self._finished = self.current >= self.total
        self._maybe_draw(force=True)

    # -- rendering ----------------------------

    def _query_term_width(self) -> int:
        try:
            return max(shutil.get_terminal_size().columns, 1)
        except Exception:
            return 80

    def _build_bar(self) -> str:
        """Build the [###...] portion. Uses sub-character rendering when smooth=True."""
        if self.smooth:
            # 8 sub-positions per cell — bar feels much smoother
            total_eighths = int((self.width * 8 * self.current) // self.total)
            total_eighths = max(0, min(total_eighths, self.width * 8))
            full = total_eighths // 8
            partial = total_eighths % 8
            bar = self.fill * full
            if full < self.width:
                if partial > 0:
                    bar += _PARTIALS[partial] + self.empty * (self.width - full - 1)
                else:
                    bar += self.empty * (self.width - full)
            return bar
        # classic block rendering for non-smooth themes
        filled = int((self.width * self.current) // self.total)
        filled = max(0, min(filled, self.width))
        return self.fill * filled + self.empty * (self.width - filled)

    def _maybe_draw(self, force: bool = False) -> None:
        """Throttle redraws to ~30 fps. Always draw on completion."""
        now = time.monotonic()
        if (
            force
            or self.current >= self.total
            or (now - self._last_draw) >= _MIN_REDRAW_INTERVAL
        ):
            self._last_draw = now
            self._draw()

    def _draw(self) -> None:
        # Non-TTY mode: stay silent except for a single line at the end.
        # Avoids spamming escape codes into pipes, log files, CI output.
        if not self._is_tty and self.current < self.total:
            return

        bar_str = self._build_bar()

        elapsed = max(time.monotonic() - self._start_time, 0.0)

        parts = []
        if self.label:
            parts.append(_close_ansi(self.label))

        if self._is_tty:
            parts.append(f"{self.color}[{bar_str}]{RESET}")
        else:
            parts.append(f"[{bar_str}]")

        percent = int((self.current * 100) // self.total)
        parts.append(f"{max(0, min(percent, 100)):3d}%")

        if self.show_speed and self.current > 0:
            if elapsed > 0:
                try:
                    speed = self.current / elapsed
                except OverflowError:
                    speed = math.inf
            else:
                speed = 0.0
            speed_str = f"{speed:.1f} it/s"
            parts.append(f"{DIM}{speed_str}{RESET}" if self._is_tty else speed_str)

        if self.show_eta and 0 < self.current < self.total:
            try:
                remaining_ratio = (self.total - self.current) / self.current
            except OverflowError:
                remaining_ratio = math.inf
            eta = elapsed * remaining_ratio if elapsed > 0 else 0.0
            eta_str = f"ETA {_format_time(eta)}"
            parts.append(f"{DIM}{eta_str}{RESET}" if self._is_tty else eta_str)
        elif self.show_eta and self.current >= self.total:
            time_str = _format_time(elapsed)
            parts.append(f"{DIM}{time_str}{RESET}" if self._is_tty else time_str)

        line = " ".join(parts)

        if self._is_tty:
            if _visible_len(line) > self._term_w:
                line = _truncate_ansi(line, self._term_w)
            _write_text(self.file, f"\r{line}\033[K")
            if self.current >= self.total:
                _write_text(self.file, "\n")
                self._line_open = False
            else:
                self._line_open = True
        else:
            # non-TTY completion: write a clean line, no escape codes
            _write_text(self.file, line + "\n")

        self.file.flush()

    def _close_line(self) -> None:
        if not self._line_open:
            return
        _write_text(self.file, "\n")
        self.file.flush()
        self._line_open = False

    def __enter__(self) -> "Bar":
        if self.current == 0 and not self._finished:
            self._start_time = time.monotonic()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._finished:
            return

        self.current = self.total
        try:
            self._draw()
        except BaseException:
            if not exc or exc[0] is None:
                raise
        finally:
            self._finished = True


# -- track() -----------------------------------------------

def track(
    iterable: Iterable[T],
    label: str = "Progress",
    total: Optional[int] = None,
    *,
    width: int = _DEFAULT_WIDTH,
    theme: str = "default",
    color: Optional[str] = None,
    fill: Optional[str] = None,
    empty: Optional[str] = None,
    show_eta: bool = True,
    show_speed: bool = False,
    smooth: Optional[bool] = None,
    file: Optional[IO[str]] = None,
) -> Iterator[T]:
    """Wrap any iterable with a progress bar.

    Usage:
        for item in track(range(100), label="Working"):
            process(item)

        for item in track(my_gen(), total=500):
            process(item)
    """
    if total is None:
        if hasattr(iterable, "__len__"):
            total = len(iterable)  # type: ignore[arg-type]
        else:
            raise TypeError(
                "iterable has no len(). Pass total= explicitly, "
                "or use Spinner for unknown-length tasks."
            )

    bar = Bar(
        total,
        width=width,
        theme=theme,
        label=label,
        color=color,
        fill=fill,
        empty=empty,
        show_eta=show_eta,
        show_speed=show_speed,
        smooth=smooth,
        file=file,
    )
    try:
        for item in iterable:
            yield item
            bar.update()
    finally:
        active_exception = sys.exc_info()[0] is not None
        try:
            bar._close_line()
        except BaseException:
            if not active_exception:
                raise
