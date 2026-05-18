from __future__ import annotations

import sys
import threading
from typing import IO, Optional

from .bar import RESET, resolve_color

SPINNER_STYLES = {
    "dots":    ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "line":    ["-", "\\", "|", "/"],
    "circle":  ["◐", "◓", "◑", "◒"],
    "bounce":  ["⠁", "⠂", "⠄", "⠂"],
    "arrows":  ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
    "grow":    ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█", "▉", "▊", "▋", "▌", "▍", "▎", "▏"],
    "moon":    ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"],
}


class Spinner:
    """Animated spinner for tasks with unknown duration.

    Args:
        label:    Text shown next to the spinner.
        style:    One of: dots, line, circle, bounce, arrows, grow, moon.
        color:    Named color or hex.
        speed:    Seconds between frames. Default 0.08.
        file:     Output stream. Default sys.stderr.

    Usage:
        with Spinner("Loading data..."):
            do_long_task()

        sp = Spinner("Working")
        sp.start()
        do_stuff()
        sp.stop("Done!")
    """

    def __init__(
        self,
        label: str = "",
        style: str = "dots",
        color: str = "cyan",
        speed: float = 0.08,
        file: Optional[IO[str]] = None,
    ) -> None:
        self.label = label
        self.frames = SPINNER_STYLES.get(style, SPINNER_STYLES["dots"])
        self.color = resolve_color(color)
        self.speed = speed
        self.file = file or sys.stderr
        self._is_tty = bool(getattr(self.file, "isatty", lambda: False)())

        # Event is the proper way to signal a thread to stop —
        # bool flag has a tiny race window between read & write.
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started = False

    def start(self) -> None:
        """Start the spinner animation in a background thread."""
        if self._started:
            return
        self._started = True
        self._stop_event.clear()
        # Skip the animation thread entirely in non-TTY environments
        # (CI, log files) — there's no live cursor to animate against.
        if self._is_tty:
            self._thread = threading.Thread(target=self._animate, daemon=True)
            self._thread.start()

    def stop(self, final_text: Optional[str] = None) -> None:
        """Stop the spinner and optionally print a final message."""
        if not self._started:
            return
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

        if self._is_tty:
            self.file.write("\r\033[K")
        if final_text:
            self.file.write(f"{final_text}\n")
        self.file.flush()
        self._started = False

    def _animate(self) -> None:
        idx = 0
        n = len(self.frames)
        while not self._stop_event.is_set():
            frame = self.frames[idx % n]
            self.file.write(f"\r{self.color}{frame}{RESET} {self.label}")
            self.file.flush()
            idx += 1
            # Event.wait is interruptible — cleaner than time.sleep
            if self._stop_event.wait(self.speed):
                break

    def __enter__(self) -> "Spinner":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            self.stop(f"✓ {self.label}")
        else:
            self.stop(f"✗ {self.label} (failed)")
        return False
