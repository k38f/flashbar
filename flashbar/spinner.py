import sys
import time
import threading

from .bar import RESET, DIM, resolve_color

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

    def __init__(self, label="", style="dots", color="cyan", speed=0.08, file=None):
        self.label = label
        self.frames = SPINNER_STYLES.get(style, SPINNER_STYLES["dots"])
        self.color = resolve_color(color)
        self.speed = speed
        self.file = file or sys.stderr

        self._running = False
        self._thread = None
        self._frame_idx = 0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self, final_text=None):
        self._running = False
        if self._thread:
            self._thread.join()
            self._thread = None

        self.file.write("\r\033[K")
        if final_text:
            self.file.write(f"{final_text}\n")
        self.file.flush()

    def _animate(self):
        while self._running:
            frame = self.frames[self._frame_idx % len(self.frames)]
            # TODO: respect terminal width here too
            self.file.write(f"\r{self.color}{frame}{RESET} {self.label}")
            self.file.flush()
            self._frame_idx += 1
            time.sleep(self.speed)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.stop(f"✓ {self.label}")
        else:
            self.stop(f"✗ {self.label} (failed)")
        return False
