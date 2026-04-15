import sys
import time
import shutil

# ── themes & colors ──────────────────────────────────────────────

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


def resolve_color(color):
    """Turn a color name ('cyan') or hex ('#FF5733') into an ANSI escape."""
    if color in NAMED_COLORS:
        return NAMED_COLORS[color]

    if isinstance(color, str) and color.startswith("#") and len(color) == 7:
        try:
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            return f"\033[38;2;{r};{g};{b}m"
        except ValueError:
            pass

    # fallback — no crash, just default blue
    return NAMED_COLORS["blue"]


def _format_time(seconds):
    """Pretty-print seconds as mm:ss or hh:mm:ss."""
    if seconds < 0:
        return "--:--"
    seconds = int(seconds)
    if seconds < 3600:
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}"


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
        file:       Output stream. Default sys.stderr.

    Usage:
        bar = Bar(100, label="Downloading")
        for i in range(100):
            bar.update()
    """

    def __init__(
        self,
        total,
        width=40,
        theme="default",
        label="",
        color=None,
        fill=None,
        empty=None,
        show_eta=True,
        show_speed=False,
        file=None,
    ):
        if total <= 0:
            raise ValueError("total must be > 0")

        self.total = total
        self.width = width
        self.label = label
        self.current = 0
        self.show_eta = show_eta
        self.show_speed = show_speed
        self.file = file or sys.stderr

        self._start_time = None
        self._finished = False

        # resolve theme + overrides
        base = THEMES.get(theme, THEMES["default"])
        self.color = resolve_color(color) if color else base["color"]
        self.fill  = fill  or base["fill"]
        self.empty = empty or base["empty"]

    def update(self, step=1):
        """Advance by `step` and redraw."""
        if self._finished:
            return

        if self._start_time is None:
            self._start_time = time.monotonic()

        self.current = min(self.current + step, self.total)
        self._draw()

        if self.current >= self.total:
            self._finished = True

    def set(self, value):
        """Jump to a specific value and redraw."""
        if self._start_time is None:
            self._start_time = time.monotonic()

        self.current = max(0, min(value, self.total))
        self._draw()

        if self.current >= self.total:
            self._finished = True

    def _draw(self):
        pct = self.current / self.total
        filled = int(self.width * pct)
        bar_str = self.fill * filled + self.empty * (self.width - filled)

        # build the line piece by piece
        parts = []
        if self.label:
            parts.append(self.label)

        parts.append(f"{self.color}[{bar_str}]{RESET}")
        parts.append(f"{int(pct * 100):3d}%")

        elapsed = time.monotonic() - self._start_time if self._start_time else 0

        if self.show_speed and self.current > 0:
            speed = self.current / elapsed if elapsed > 0 else 0
            parts.append(f"{DIM}{speed:.1f} it/s{RESET}")

        if self.show_eta and self.current > 0 and self.current < self.total:
            eta = (elapsed / self.current) * (self.total - self.current)
            parts.append(f"{DIM}ETA {_format_time(eta)}{RESET}")
        elif self.show_eta and self.current >= self.total:
            parts.append(f"{DIM}{_format_time(elapsed)}{RESET}")

        line = " ".join(parts)

        # truncate if wider than terminal (avoid ugly wrapping)
        try:
            term_w = shutil.get_terminal_size().columns
            # strip ANSI for length check — rough but good enough
            visible = line
            import re
            visible = re.sub(r"\033\[[0-9;]*m", "", visible)
            if len(visible) > term_w:
                line = line[:term_w]
        except Exception:
            pass

        self.file.write(f"\r{line}\033[K")
        self.file.flush()

        if self.current >= self.total:
            self.file.write("\n")

    # context manager — auto-finish on exit
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if not self._finished:
            self.current = self.total
            self._draw()
            self._finished = True
        return False


def track(iterable, label="Progress", total=None, **kwargs):
    """Wrap any iterable with a progress bar.

    Handles generators/iterators that don't have __len__ —
    just pass `total` explicitly.

    Usage:
        for item in track(range(100), label="Working"):
            process(item)

        # generators — pass total manually
        for item in track(my_gen(), total=500):
            process(item)
    """
    if total is None:
        if hasattr(iterable, "__len__"):
            total = len(iterable)
        else:
            raise TypeError(
                "iterable has no len(). Pass total= explicitly, "
                "or use Spinner for unknown-length tasks."
            )

    bar = Bar(total, label=label, **kwargs)
    for item in iterable:
        yield item
        bar.update()
