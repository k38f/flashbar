from __future__ import annotations

import math
import os
import shutil
import sys
import threading
import unicodedata
from typing import IO, Iterable, Literal, Optional, Tuple

from .bar import RESET, _truncate_ansi, _visible_len, resolve_color

SPINNER_STYLES = {
    "dots":    ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "line":    ["-", "\\", "|", "/"],
    "circle":  ["◐", "◓", "◑", "◒"],
    "bounce":  ["⠁", "⠂", "⠄", "⠂"],
    "arrows":  ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
    "grow":    ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█", "▉", "▊", "▋", "▌", "▍", "▎", "▏"],
    "moon":    ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"],
}

_ASCII_STATUS = str.maketrans({"✓": "OK", "✗": "X"})
_DEFAULT_TERM_WIDTH = 80


def _valid_speed(value: float) -> float:
    try:
        speed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("speed must be a finite number > 0") from exc

    if not math.isfinite(speed) or speed <= 0:
        raise ValueError("speed must be a finite number > 0")
    return speed


def _copy_frames(frames: Iterable[str]) -> Tuple[str, ...]:
    if isinstance(frames, (str, bytes)):
        raise ValueError("spinner frames must be a non-empty sequence of strings")

    try:
        result = tuple(frames)
    except TypeError as exc:
        raise ValueError("spinner frames must be a non-empty sequence of strings") from exc

    if not result:
        raise ValueError("spinner style must contain at least one frame")
    for frame in result:
        if not isinstance(frame, str) or not frame:
            raise ValueError("spinner frames must be non-empty strings")
        if any(ord(char) < 32 or ord(char) == 127 for char in frame):
            raise ValueError("spinner frames must not contain control characters")
    return result


def _single_line(text: str) -> str:
    out = []
    for char in text:
        category = unicodedata.category(char)
        if char in "\r\n\t" or category == "Cc":
            out.append(" ")
        elif category == "Cs":
            out.append("?")
        else:
            out.append(char)
    return "".join(out)


def _visible_width(text: str) -> int:
    return _visible_len(text)


def _clip_cells(text: str, max_width: int) -> str:
    return _truncate_ansi(text, max_width)


def _encoding_fallback(text: str, encoding: str) -> str:
    text = text.translate(_ASCII_STATUS)
    try:
        return text.encode(encoding, errors="replace").decode(encoding)
    except (LookupError, UnicodeError):
        return text.encode("ascii", errors="replace").decode("ascii")


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
        raw_frames = SPINNER_STYLES.get(style)
        if raw_frames is None:
            raw_frames = SPINNER_STYLES.get("dots")
        if raw_frames is None:
            raise ValueError("default spinner style must contain frames")

        self.label = label
        self.frames = _copy_frames(raw_frames)
        self.color = resolve_color(color)
        self.speed = _valid_speed(speed)
        self.file = sys.stderr if file is None else file
        self._is_tty = self._stream_is_tty()

        self._condition = threading.Condition(threading.RLock())
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started = False
        self._state = "idle"
        self._stop_owner: Optional[int] = None
        self._generation = 0
        self._worker_error: Optional[BaseException] = None

    def start(self) -> None:
        """Start the spinner animation in a background thread."""
        current_ident = threading.get_ident()
        with self._condition:
            while self._state == "stopping":
                if self._stop_owner == current_ident:
                    raise RuntimeError("cannot restart a spinner while it is stopping")
                self._condition.wait()

            if self._state == "running":
                if self._worker_error is not None:
                    raise self._worker_error
                return

            frames = _copy_frames(self.frames)
            speed = _valid_speed(self.speed)
            label = _single_line(str(self.label))
            color = self.color
            is_tty = self._stream_is_tty()

            self.speed = speed
            self._is_tty = is_tty
            self._stop_event = threading.Event()
            self._worker_error = None
            self._generation += 1
            generation = self._generation
            self._state = "running"
            self._started = True

            if not is_tty:
                self._thread = None
                return

            thread = threading.Thread(
                target=self._animate,
                args=(self._stop_event, frames, speed, label, color, generation),
                name="flashbar-spinner",
                daemon=True,
            )
            self._thread = thread
            try:
                # Starting under the lock keeps stop() from joining an unstarted thread.
                thread.start()
            except BaseException:
                self._stop_event.set()
                self._thread = None
                self._state = "idle"
                self._started = False
                self._condition.notify_all()
                raise

    def stop(self, final_text: Optional[str] = None) -> None:
        """Stop the spinner and optionally print a final message."""
        current_ident = threading.get_ident()
        with self._condition:
            if self._state == "stopping":
                if self._stop_owner == current_ident:
                    return
                generation = self._generation
                while self._state == "stopping" and self._generation == generation:
                    self._condition.wait()
                return

            if self._state != "running":
                return
            if self._thread is threading.current_thread():
                raise RuntimeError("spinner cannot be stopped from its animation thread")

            generation = self._generation
            event = self._stop_event
            thread = self._thread
            was_tty = self._is_tty
            self._state = "stopping"
            self._stop_owner = current_ident
            event.set()

        worker_error: Optional[BaseException] = None
        output_error: Optional[BaseException] = None
        try:
            if thread is not None:
                thread.join()

            with self._condition:
                if self._generation == generation:
                    worker_error = self._worker_error

            try:
                if was_tty:
                    self._write_text("\r\033[2K")
                if final_text:
                    self._write_text(f"{final_text}\n")
                self.file.flush()
            except BaseException as exc:
                output_error = exc
        finally:
            with self._condition:
                if self._generation == generation:
                    if worker_error is None:
                        worker_error = self._worker_error
                    self._thread = None
                    self._worker_error = None
                    self._state = "idle"
                    self._started = False
                    self._stop_owner = None
                    self._condition.notify_all()

        if worker_error is not None:
            raise worker_error
        if output_error is not None:
            raise output_error

    def _animate(
        self,
        event: threading.Event,
        frames: Tuple[str, ...],
        speed: float,
        label: str,
        color: str,
        generation: int,
    ) -> None:
        idx = 0
        try:
            while not event.is_set():
                frame = frames[idx % len(frames)]
                self._write_text(self._render_frame(frame, label, color))
                self.file.flush()
                idx += 1
                if event.wait(speed):
                    break
        except BaseException as exc:
            with self._condition:
                if self._generation == generation and self._stop_event is event:
                    self._worker_error = exc
            event.set()

    def _render_frame(self, frame: str, label: str, color: str) -> str:
        terminal_width = self._terminal_width()
        clipped_frame = _clip_cells(frame, terminal_width)
        used = _visible_width(clipped_frame)

        clipped_label = ""
        if label and used < terminal_width:
            remaining = terminal_width - used - 1
            if remaining > 0:
                clipped_label = _clip_cells(label, remaining)

        content = f"{color}{clipped_frame}{RESET}"
        if clipped_label:
            content += f" {clipped_label}"
        return f"\r\033[2K{content}"

    def _stream_is_tty(self) -> bool:
        try:
            return bool(getattr(self.file, "isatty", lambda: False)())
        except (OSError, TypeError, ValueError):
            return False

    def _terminal_width(self) -> int:
        try:
            columns = os.get_terminal_size(self.file.fileno()).columns
        except (AttributeError, OSError, TypeError, ValueError):
            columns = shutil.get_terminal_size(
                fallback=(_DEFAULT_TERM_WIDTH, 24)
            ).columns
        return max(1, columns)

    def _write_text(self, text: str) -> None:
        encoding = getattr(self.file, "encoding", None)
        if isinstance(encoding, str):
            try:
                text.encode(encoding)
            except (LookupError, UnicodeEncodeError):
                text = _encoding_fallback(text, encoding)

        try:
            self.file.write(text)
        except UnicodeEncodeError as exc:
            fallback_encoding = getattr(exc, "encoding", None) or encoding or "ascii"
            fallback = _encoding_fallback(text, fallback_encoding)
            if fallback == text:
                raise
            self.file.write(fallback)

    def __enter__(self) -> "Spinner":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> Literal[False]:
        label = _single_line(str(self.label))
        if exc_type is None:
            self.stop(f"✓ {label}")
        else:
            try:
                self.stop(f"✗ {label} (failed)")
            except BaseException:
                # Output failures should never replace the user's exception.
                pass
        return False
