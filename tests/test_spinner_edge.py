import importlib
import re
import threading

import pytest

from flashbar import SPINNER_STYLES, Spinner


spinner_module = importlib.import_module("flashbar.spinner")
ANSI_RE = re.compile(r"\033\[[0-9;]*[A-Za-z]")


def wait_for(event, message="background operation did not finish"):
    assert event.wait(2), message


def join_thread(thread):
    thread.join(2)
    assert not thread.is_alive(), "test thread did not stop"


class RecordingStream:
    def __init__(self, tty=True, encoding="utf-8"):
        self.tty = tty
        self.encoding = encoding
        self.writes = []
        self.animation_written = threading.Event()
        self._lock = threading.Lock()

    def isatty(self):
        return self.tty

    def write(self, text):
        text.encode(self.encoding)
        with self._lock:
            self.writes.append(text)
            if text.startswith("\r\033[2K"):
                self.animation_written.set()
        return len(text)

    def flush(self):
        pass

    def snapshot(self):
        with self._lock:
            return list(self.writes)


@pytest.mark.parametrize(
    "speed",
    [0, -0.01, float("nan"), float("inf"), float("-inf"), None, "fast"],
)
def test_speed_has_to_be_positive_and_finite(speed):
    with pytest.raises(ValueError, match="speed"):
        Spinner(speed=speed)


def test_invalid_speed_changed_after_init_is_rejected():
    spinner = Spinner(file=RecordingStream(tty=False))
    spinner.speed = 0

    with pytest.raises(ValueError, match="speed"):
        spinner.start()
    assert spinner._started is False


def test_frames_are_copied_from_mutable_style(monkeypatch):
    frames = ["a", "b"]
    monkeypatch.setitem(SPINNER_STYLES, "temporary", frames)
    stream = RecordingStream()
    spinner = Spinner(style="temporary", speed=10, file=stream)
    frames.clear()

    assert spinner.frames == ("a", "b")
    spinner.start()
    wait_for(stream.animation_written)
    spinner.stop()


@pytest.mark.parametrize("frames", [[], [""], ["ok", "bad\nframe"], [1]])
def test_broken_spinner_styles_fail_before_worker_starts(monkeypatch, frames):
    monkeypatch.setitem(SPINNER_STYLES, "broken", frames)
    with pytest.raises(ValueError, match="frame|style"):
        Spinner(style="broken")


def test_frames_changed_after_init_are_checked_on_start():
    spinner = Spinner(file=RecordingStream(tty=False))
    spinner.frames = ()

    with pytest.raises(ValueError, match="frame|style"):
        spinner.start()
    assert spinner._started is False


def test_falsey_output_stream_is_not_replaced_with_stderr():
    class FalseyStream(RecordingStream):
        def __bool__(self):
            return False

    stream = FalseyStream(tty=False)
    spinner = Spinner(file=stream)
    spinner.start()
    spinner.stop("done")

    assert spinner.file is stream
    assert stream.snapshot() == ["done\n"]


def test_tty_state_is_refreshed_for_each_run():
    stream = RecordingStream(tty=False)
    spinner = Spinner(speed=10, file=stream)

    spinner.start()
    spinner.stop()
    assert stream.snapshot() == []

    stream.tty = True
    spinner.start()
    wait_for(stream.animation_written)
    spinner.stop()

    assert any(text.startswith("\r\033[2K") for text in stream.snapshot())
    assert spinner._is_tty is True


def test_stop_cannot_join_thread_before_start_returns(monkeypatch):
    real_thread = threading.Thread
    start_entered = threading.Event()
    allow_start = threading.Event()
    stop_attempted = threading.Event()
    errors = []

    class SlowStartThread(real_thread):
        def start(self):
            start_entered.set()
            wait_for(allow_start, "test did not release Thread.start")
            super().start()

    monkeypatch.setattr(spinner_module.threading, "Thread", SlowStartThread)
    spinner = Spinner(style="line", speed=10, file=RecordingStream())

    def call_start():
        try:
            spinner.start()
        except BaseException as exc:
            errors.append(exc)

    def call_stop():
        stop_attempted.set()
        try:
            spinner.stop()
        except BaseException as exc:
            errors.append(exc)

    starter = real_thread(target=call_start)
    stopper = real_thread(target=call_stop)
    starter.start()
    wait_for(start_entered)
    stopper.start()
    wait_for(stop_attempted)
    allow_start.set()

    join_thread(starter)
    join_thread(stopper)
    assert errors == []
    assert spinner._started is False
    assert spinner._thread is None


def test_concurrent_stop_only_prints_one_final_message():
    final_entered = threading.Event()
    release_final = threading.Event()
    lock = threading.Lock()

    class BlockingFinalStream(RecordingStream):
        def __init__(self):
            super().__init__(tty=False)

        def write(self, text):
            if text == "done\n":
                final_entered.set()
                wait_for(release_final, "test did not release final write")
            return super().write(text)

    stream = BlockingFinalStream()
    spinner = Spinner(file=stream)
    spinner.start()
    barrier = threading.Barrier(3)
    errors = []

    def stop_it():
        barrier.wait()
        try:
            spinner.stop("done")
        except BaseException as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=stop_it) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    wait_for(final_entered)
    release_final.set()
    for thread in threads:
        join_thread(thread)

    assert errors == []
    assert stream.snapshot().count("done\n") == 1


def test_worker_write_error_is_raised_by_stop_and_state_can_restart():
    failed = threading.Event()

    class FailFirstWrite(RecordingStream):
        def __init__(self):
            super().__init__()
            self.fail_next = True

        def write(self, text):
            if self.fail_next:
                self.fail_next = False
                failed.set()
                raise OSError("worker write failed")
            return super().write(text)

    stream = FailFirstWrite()
    spinner = Spinner(style="line", speed=10, file=stream)
    spinner.start()
    wait_for(failed)
    join_thread(spinner._thread)

    with pytest.raises(OSError, match="worker write failed"):
        spinner.start()

    with pytest.raises(OSError, match="worker write failed"):
        spinner.stop()
    assert spinner._started is False
    assert spinner._thread is None

    stream.animation_written.clear()
    spinner.start()
    wait_for(stream.animation_written)
    spinner.stop()


def test_worker_flush_error_is_not_lost():
    failed = threading.Event()

    class FailFirstFlush(RecordingStream):
        def __init__(self):
            super().__init__()
            self.fail_next = True

        def flush(self):
            if self.fail_next:
                self.fail_next = False
                failed.set()
                raise OSError("worker flush failed")

    stream = FailFirstFlush()
    spinner = Spinner(style="line", speed=10, file=stream)
    spinner.start()
    wait_for(failed)

    with pytest.raises(OSError, match="worker flush failed"):
        spinner.stop()
    assert spinner._started is False
    assert spinner._thread is None


def test_final_write_error_still_resets_lifecycle():
    class FailOnceStream(RecordingStream):
        def __init__(self):
            super().__init__(tty=False)
            self.fail_next = True

        def write(self, text):
            if self.fail_next:
                self.fail_next = False
                raise OSError("final write failed")
            return super().write(text)

    stream = FailOnceStream()
    spinner = Spinner(file=stream)
    spinner.start()
    with pytest.raises(OSError, match="final write failed"):
        spinner.stop("first")

    assert spinner._started is False
    assert spinner._thread is None
    spinner.start()
    spinner.stop("second")
    assert stream.snapshot() == ["second\n"]


def test_legacy_encoding_gets_ascii_safe_frames_and_status():
    stream = RecordingStream(encoding="cp1251")
    spinner = Spinner("готово", speed=10, file=stream)

    with spinner:
        wait_for(stream.animation_written)

    output = "".join(stream.snapshot())
    assert "✓" not in output
    assert "OK готово" in output
    output.encode("cp1251")


def test_output_failure_does_not_mask_exception_from_context():
    class BrokenStream(RecordingStream):
        def __init__(self):
            super().__init__(tty=False, encoding="ascii")

        def write(self, text):
            raise UnicodeEncodeError("ascii", text, 0, 1, "no output")

    class UserError(Exception):
        pass

    spinner = Spinner("ошибка", file=BrokenStream())
    with pytest.raises(UserError, match="user failure"):
        with spinner:
            raise UserError("user failure")

    assert spinner._started is False
    assert spinner._thread is None


def test_worker_error_does_not_mask_exception_from_context():
    worker_failed = threading.Event()

    class BrokenWorker(RecordingStream):
        def write(self, text):
            worker_failed.set()
            raise OSError("background output failed")

    class UserError(Exception):
        pass

    spinner = Spinner(style="line", speed=10, file=BrokenWorker())
    with pytest.raises(UserError, match="task failed"):
        with spinner:
            wait_for(worker_failed)
            raise UserError("task failed")

    assert spinner._started is False


def test_long_multiline_label_stays_on_one_terminal_line():
    stream = RecordingStream()
    spinner = Spinner("first\n界界界界 and a very long tail", speed=10, file=stream)
    spinner._terminal_width = lambda: 12

    spinner.start()
    wait_for(stream.animation_written)
    animation = stream.snapshot()[0]
    spinner.stop()

    visible = ANSI_RE.sub("", animation).lstrip("\r")
    assert animation.startswith("\r\033[2K")
    assert "\n" not in animation
    assert "\r" not in animation[1:]
    assert spinner_module._visible_width(visible) <= 12
    assert all(
        not text.startswith("\r") or text.startswith("\r\033[2K")
        for text in stream.snapshot()
    )


def test_zwj_emoji_is_not_split_when_label_is_clipped():
    spinner = Spinner(style="line", speed=10, file=RecordingStream())
    spinner._terminal_width = lambda: 5

    rendered = spinner._render_frame("-", "👩‍💻x", "")
    visible = ANSI_RE.sub("", rendered).lstrip("\r")

    assert "👩‍💻x" in visible
    assert spinner_module._visible_width(visible) <= 5
