from __future__ import annotations

import re
import shutil
import sys
import time
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

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
_DEFAULT_WIDTH = 40
_MIN_REDRAW_INTERVAL = 1.0 / 30.0  # cap redraws at ~30 fps


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
    if seconds < 0:
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


def _visible_len(text: str) -> int:
    return len(_ANSI_RE.sub("", text))


def _truncate_ansi(line: str, max_visible: int) -> str:
    """Truncate `line` to `max_visible` visible characters, preserving ANSI codes."""
    out = []
    visible = 0
    i = 0
    n = len(line)
    while i < n and visible < max_visible:
        m = _ANSI_RE.match(line, i)
        if m:
            out.append(m.group())
            i = m.end()
        else:
            out.append(line[i])
            visible += 1
            i += 1
    return "".join(out) + RESET


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
        if total <= 0:
            raise ValueError("total must be > 0")

        self.total = total
        self.width = width
        self.label = label
        self.current = 0
        self.show_eta = show_eta
        self.show_speed = show_speed
        self.file = file or sys.stderr

        # Disable colors/animation when output isn't a real terminal —
        # avoids spamming escape codes into log files and CI output.
        self._is_tty = bool(getattr(self.file, "isatty", lambda: False)())

        # Cache terminal width so we don't syscall on every redraw.
        self._term_w = self._query_term_width()

        self._start_time: Optional[float] = None
        self._finished = False
        self._last_draw = 0.0

        base = THEMES.get(theme, THEMES["default"])
        self.color = resolve_color(color) if color else base["color"]
        self.fill  = fill  or base["fill"]
        self.empty = empty or base["empty"]

        # Auto-enable smooth rendering when the fill is a full block.
        if smooth is None:
            smooth = (self.fill == "█")
        self.smooth = smooth

    # -- public api ----------------------------------------

    def update(self, step: int = 1) -> None:
        """Advance by `step` and redraw."""
        if self._finished:
            return

        if self._start_time is None:
            self._start_time = time.monotonic()

        self.current = min(self.current + step, self.total)
        self._maybe_draw()

        if self.current >= self.total:
            self._finished = True

    def set(self, value: int) -> None:
        """Jump to a specific value and redraw."""
        if self._start_time is None:
            self._start_time = time.monotonic()

        self.current = max(0, min(int(value), self.total))
        self._maybe_draw()

        if self.current >= self.total:
            self._finished = True

    # -- rendering ----------------------------

    def _query_term_width(self) -> int:
        try:
            return shutil.get_terminal_size().columns
        except Exception:
            return 80

    def _build_bar(self, pct: float) -> str:
        """Build the [###...] portion. Uses sub-character rendering when smooth=True."""
        if self.smooth:
            # 8 sub-positions per cell — bar feels much smoother
            total_eighths = int(self.width * 8 * pct)
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
        filled = int(self.width * pct)
        return self.fill * filled + self.empty * (self.width - filled)

    def _maybe_draw(self) -> None:
        """Throttle redraws to ~30 fps. Always draw on completion."""
        now = time.monotonic()
        if self.current >= self.total or (now - self._last_draw) >= _MIN_REDRAW_INTERVAL:
            self._last_draw = now
            self._draw()

    def _draw(self) -> None:
        # Non-TTY mode: stay silent except for a single line at the end.
        # Avoids spamming escape codes into pipes, log files, CI output.
        if not self._is_tty and self.current < self.total:
            return

        pct = self.current / self.total
        bar_str = self._build_bar(pct)

        elapsed = time.monotonic() - self._start_time if self._start_time else 0.0

        parts = []
        if self.label:
            parts.append(self.label)

        if self._is_tty:
            parts.append(f"{self.color}[{bar_str}]{RESET}")
        else:
            parts.append(f"[{bar_str}]")

        parts.append(f"{int(pct * 100):3d}%")

        if self.show_speed and self.current > 0:
            speed = self.current / elapsed if elapsed > 0 else 0.0
            speed_str = f"{speed:.1f} it/s"
            parts.append(f"{DIM}{speed_str}{RESET}" if self._is_tty else speed_str)

        if self.show_eta and 0 < self.current < self.total:
            eta = (elapsed / self.current) * (self.total - self.current)
            eta_str = f"ETA {_format_time(eta)}"
            parts.append(f"{DIM}{eta_str}{RESET}" if self._is_tty else eta_str)
        elif self.show_eta and self.current >= self.total:
            time_str = _format_time(elapsed)
            parts.append(f"{DIM}{time_str}{RESET}" if self._is_tty else time_str)

        line = " ".join(parts)

        if self._is_tty:
            if _visible_len(line) > self._term_w:
                line = _truncate_ansi(line, self._term_w)
            self.file.write(f"\r{line}\033[K")
            if self.current >= self.total:
                self.file.write("\n")
        else:
            # non-TTY completion: write a clean line, no escape codes
            self.file.write(line + "\n")

        self.file.flush()

    def __enter__(self) -> "Bar":
        return self

    def __exit__(self, *exc) -> bool:
        if not self._finished:
            self.current = self.total
            self._draw()
            self._finished = True
        return False


# -- track() -----------------------------------------------

def track(
    iterable: Iterable[T],
    label: str = "Progress",
    total: Optional[int] = None,
    **kwargs,
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

    bar = Bar(total, label=label, **kwargs)
    for item in iterable:
        yield item
        bar.update()
