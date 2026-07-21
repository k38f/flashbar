from __future__ import annotations

import math
import re
import shutil
import sys
import time
import unicodedata
from collections.abc import Mapping
from typing import IO, Iterable, Iterator, List, Optional, TypeVar, Union

from .update_check import _maybe_notify_once

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
_DECIMAL_PREFIXES = ("", "k", "M", "G", "T", "P", "E", "Z", "Y")
_BINARY_PREFIXES = ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi", "Yi")


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


def _single_line(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ")


def _format_postfix(values: Mapping[str, object]) -> str:
    parts: List[str] = list(
        _close_ansi(f"{_single_line(key)}={_single_line(value)}")
        for key, value in values.items()
    )
    return " ".join(parts)


def _format_integer(value: int) -> str:
    try:
        return str(value)
    except ValueError:
        if value == 0:
            return "0"
        logarithm = math.log10(abs(value))
        exponent = int(math.floor(logarithm))
        mantissa = 10 ** (logarithm - exponent)
        sign = "-" if value < 0 else ""
        return f"{sign}{mantissa:.1f}e+{exponent}"


def _format_measure(value: Union[int, float], unit: str, scale: bool) -> str:
    if not scale:
        if isinstance(value, int):
            number = _format_integer(value)
        else:
            try:
                number = f"{float(value):.1f}"
            except (TypeError, ValueError, OverflowError):
                number = str(value)
        return f"{number} {unit}".rstrip()

    base = 1024 if unit == "B" else 1000
    prefixes = _BINARY_PREFIXES if base == 1024 else _DECIMAL_PREFIXES
    try:
        amount = float(value)
    except (TypeError, ValueError, OverflowError):
        if not isinstance(value, int) or value == 0:
            return f"{type(value).__name__} {unit}".rstrip()
        logarithm = math.log(abs(value), base)
        prefix_index = min(int(logarithm), len(prefixes) - 1)
        scaled_logarithm = (
            math.log10(abs(value)) - prefix_index * math.log10(base)
        )
        exponent = int(math.floor(scaled_logarithm))
        mantissa = 10 ** (scaled_logarithm - exponent)
        sign = "-" if value < 0 else ""
        number = f"{sign}{mantissa:.1f}e+{exponent}"
        return f"{number} {prefixes[prefix_index]}{unit}".rstrip()

    prefix_index = 0
    while (
        math.isfinite(amount)
        and abs(amount) >= base
        and prefix_index < len(prefixes) - 1
    ):
        amount /= base
        prefix_index += 1

    if (
        math.isfinite(amount)
        and abs(round(amount, 1)) >= base
        and prefix_index < len(prefixes) - 1
    ):
        amount /= base
        prefix_index += 1

    if prefix_index == 0 and isinstance(value, int):
        number = _format_integer(value)
    elif math.isfinite(amount):
        number = f"{amount:.1f}"
    else:
        number = str(amount)
    return f"{number} {prefixes[prefix_index]}{unit}".rstrip()


# ---------------------------------------------------------

class Bar:
    """Terminal progress bar with ETA, speed, and themes.

    Args:
        total:      Number of steps to complete, or None when unknown.
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
        unit:       Optional unit shown with progress, such as "B" or "files".
        unit_scale: Scale large values (B uses KiB, MiB, and so on).
        transient:  Remove the completed bar from an interactive terminal.

    Usage:
        bar = Bar(100, label="Downloading")
        for i in range(100):
            bar.update()
    """

    def __init__(
        self,
        total: Optional[int],
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
        unit: Optional[str] = None,
        unit_scale: bool = False,
        transient: bool = False,
    ) -> None:
        if total is not None and (
            isinstance(total, bool) or not isinstance(total, int)
        ):
            raise TypeError("total must be an integer")
        if total is not None and total <= 0:
            raise ValueError("total must be > 0")
        if isinstance(width, bool) or not isinstance(width, int):
            raise TypeError("width must be an integer")
        if width <= 0:
            raise ValueError("width must be > 0")
        if unit is not None and not isinstance(unit, str):
            raise TypeError("unit must be a string")
        if not isinstance(unit_scale, bool):
            raise TypeError("unit_scale must be a boolean")
        if not isinstance(transient, bool):
            raise TypeError("transient must be a boolean")

        self.total = total
        self.width = width
        self.label = _single_line(label)
        self.postfix = ""
        raw_unit = _single_line(unit) if unit is not None else "it"
        self.unit = _ANSI_RE.sub("", raw_unit)
        self.unit_scale = unit_scale
        self._show_units = unit is not None or unit_scale
        self.transient = transient
        self.current = 0
        self.show_eta = show_eta
        self.show_speed = show_speed
        self._uses_default_file = file is None
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
        self._in_context = False

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

        if self.total is None:
            self.current += step
        else:
            self.current = min(self.current + step, self.total)
        self._maybe_draw()

        if self.total is not None and self.current >= self.total:
            self._finished = True
            if self._uses_default_file and not self._in_context:
                _maybe_notify_once(self.file)

    def set(self, value: int) -> None:
        """Jump to a specific value and redraw."""
        if self.total is None:
            new_value = max(0, int(value))
            if self._finished:
                self._start_time = time.monotonic()
                self._finished = False
            self.current = new_value
            self._maybe_draw(force=True)
            return

        new_value = max(0, min(int(value), self.total))
        if self._finished and new_value >= self.total:
            return
        if self._finished:
            self._start_time = time.monotonic()
        self.current = new_value
        self._finished = self.current >= self.total
        self._maybe_draw(force=True)
        if self._finished and self._uses_default_file and not self._in_context:
            _maybe_notify_once(self.file)

    def set_total(self, total: int) -> None:
        """Set a known total and switch an indeterminate bar to percentages."""
        if isinstance(total, bool) or not isinstance(total, int):
            raise TypeError("total must be an integer")
        if total <= 0:
            raise ValueError("total must be > 0")
        if self.total == total:
            return

        was_finished = self._finished
        self.total = total
        self.current = min(self.current, total)
        self._finished = self.current >= total
        if was_finished and not self._finished:
            self._start_time = time.monotonic()
        self._maybe_draw(force=True)

        if self._finished and self._uses_default_file and not self._in_context:
            _maybe_notify_once(self.file)

    def set_label(self, label: object) -> None:
        self.label = _single_line(label)
        if not self._finished:
            self._maybe_draw(force=True)

    def set_postfix(self, **values: object) -> None:
        self.postfix = _format_postfix(values)
        if not self._finished:
            self._maybe_draw(force=True)

    # -- rendering ----------------------------

    def _query_term_width(self) -> int:
        try:
            return max(shutil.get_terminal_size().columns, 1)
        except Exception:
            return 80

    def _build_bar(self) -> str:
        """Build the [###...] portion. Uses sub-character rendering when smooth=True."""
        if self.total is None:
            if self._finished:
                return self.fill * self.width
            pulse_width = min(3, self.width)
            travel = self.width - pulse_width
            if travel == 0:
                position = 0
            else:
                phase = self.current % (travel * 2)
                position = phase if phase <= travel else travel * 2 - phase
            return (
                self.empty * position
                + self.fill * pulse_width
                + self.empty * (self.width - position - pulse_width)
            )

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
            or self._finished
            or (self.total is not None and self.current >= self.total)
            or (now - self._last_draw) >= _MIN_REDRAW_INTERVAL
        ):
            self._last_draw = now
            self._draw()

    def _draw(self) -> None:
        complete = self._finished or (
            self.total is not None and self.current >= self.total
        )
        # Non-TTY mode: stay silent except for a single line at the end.
        # Avoids spamming escape codes into pipes, log files, CI output.
        if not self._is_tty and not complete:
            return
        if not self._is_tty and self.transient:
            return

        bar_str = self._build_bar()

        elapsed = max(time.monotonic() - self._start_time, 0.0)

        parts = []
        if self.label:
            label = _close_ansi(self.label) if self._is_tty else _ANSI_RE.sub(
                "", self.label
            )
            parts.append(label)

        if self._is_tty:
            parts.append(f"{self.color}[{bar_str}]{RESET}")
        else:
            parts.append(f"[{bar_str}]")

        if self.total is not None:
            percent = int((self.current * 100) // self.total)
            parts.append(f"{max(0, min(percent, 100)):3d}%")

        if self.total is None:
            parts.append(
                _format_measure(self.current, self.unit, self.unit_scale)
            )
        elif self._show_units:
            if self.unit_scale:
                current = _format_measure(self.current, self.unit, True)
                total = _format_measure(self.total, self.unit, True)
                parts.append(f"{current} / {total}")
            else:
                current = _format_integer(self.current)
                total = _format_integer(self.total)
                count = f"{current} / {total}"
                parts.append(f"{count} {self.unit}".rstrip())

        if self.show_speed and self.current > 0:
            if elapsed > 0:
                try:
                    speed = self.current / elapsed
                except OverflowError:
                    speed = math.inf
            else:
                speed = 0.0
            if self._show_units or self.total is None:
                speed_str = (
                    f"{_format_measure(speed, self.unit, self.unit_scale)}/s"
                )
            else:
                speed_str = f"{speed:.1f} it/s"
            parts.append(f"{DIM}{speed_str}{RESET}" if self._is_tty else speed_str)

        if (
            self.total is not None
            and self.show_eta
            and 0 < self.current < self.total
        ):
            try:
                remaining_ratio = (self.total - self.current) / self.current
            except OverflowError:
                remaining_ratio = math.inf
            eta = elapsed * remaining_ratio if elapsed > 0 else 0.0
            eta_str = f"ETA {_format_time(eta)}"
            parts.append(f"{DIM}{eta_str}{RESET}" if self._is_tty else eta_str)
        elif (
            self.total is not None
            and self.show_eta
            and self.current >= self.total
        ):
            time_str = _format_time(elapsed)
            parts.append(f"{DIM}{time_str}{RESET}" if self._is_tty else time_str)
        elif self.total is None and self.show_eta and complete:
            time_str = _format_time(elapsed)
            parts.append(f"{DIM}{time_str}{RESET}" if self._is_tty else time_str)

        if self.postfix:
            postfix = (
                _close_ansi(self.postfix)
                if self._is_tty
                else _ANSI_RE.sub("", self.postfix)
            )
            parts.append(postfix)

        line = " ".join(parts)

        if self._is_tty:
            if _visible_len(line) > self._term_w:
                line = _truncate_ansi(line, self._term_w)
            _write_text(self.file, f"\r{line}\033[K")
            if complete:
                if self.transient:
                    _write_text(self.file, "\r\033[2K")
                else:
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
        if self.transient and self._is_tty:
            _write_text(self.file, "\r\033[2K")
        else:
            _write_text(self.file, "\n")
        self.file.flush()
        self._line_open = False

    def __enter__(self) -> "Bar":
        if self.current == 0 and not self._finished:
            self._start_time = time.monotonic()
        self._in_context = True
        return self

    def __exit__(self, *exc: object) -> None:
        clean_exit = not exc or exc[0] is None
        self._in_context = False
        if self._finished:
            if clean_exit and self._uses_default_file:
                _maybe_notify_once(self.file)
            return

        if self.total is None:
            self._finished = True
        else:
            self.current = self.total
        draw_succeeded = False
        try:
            self._draw()
            draw_succeeded = True
        except BaseException:
            if not exc or exc[0] is None:
                raise
        finally:
            self._finished = True

        if draw_succeeded and clean_exit:
            if self._uses_default_file:
                _maybe_notify_once(self.file)


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
    unit: Optional[str] = None,
    unit_scale: bool = False,
    transient: bool = False,
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
        unit=unit,
        unit_scale=unit_scale,
        transient=transient,
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
