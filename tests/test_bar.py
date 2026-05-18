"""Tests for flashbar core functionality."""
import io
import time
import pytest
from flashbar import Bar, track, Spinner
from flashbar.bar import _format_time, resolve_color, _truncate_ansi


# -- Bar tests ---------------------------------------------------------

class TestBar:
    def test_basic_creation(self):
        bar = Bar(100)
        assert bar is not None
        assert bar.total == 100
        assert bar.current == 0

    def test_update_runs_to_completion(self):
        bar = Bar(10)
        for _ in range(10):
            bar.update()
        assert bar.current == 10
        assert bar._finished

    def test_set_jumps_to_value(self):
        bar = Bar(100)
        bar.set(50)
        assert bar.current == 50
        bar.set(100)
        assert bar.current == 100
        assert bar._finished

    def test_set_beyond_total_no_crash(self):
        bar = Bar(10)
        bar.set(20)
        assert bar.current == 10  # clamped

    def test_update_past_total_no_crash(self):
        bar = Bar(5)
        for _ in range(10):
            bar.update()
        assert bar.current == 5

    def test_context_manager(self):
        with Bar(10) as bar:
            for _ in range(10):
                bar.update()
        assert bar._finished

    def test_context_manager_handles_exception(self):
        with pytest.raises(ValueError):
            with Bar(10) as bar:
                bar.update()
                raise ValueError("boom")

    def test_all_themes(self):
        themes = ["default", "green", "red", "retro",
                  "minimal", "slim", "dots", "arrow"]
        for theme in themes:
            bar = Bar(10, theme=theme)
            for _ in range(10):
                bar.update()

    def test_named_color(self):
        bar = Bar(10, color="cyan")
        bar.update()

    def test_hex_color(self):
        bar = Bar(10, color="#FF5733")
        bar.update()

    def test_custom_fill_and_empty(self):
        bar = Bar(10, fill="▓", empty="▒")
        for _ in range(10):
            bar.update()

    def test_eta_and_speed_flags(self):
        bar = Bar(10, show_eta=True, show_speed=True)
        for _ in range(10):
            bar.update()

    def test_zero_total(self):
        with pytest.raises(ValueError):
            Bar(0)

    def test_negative_total(self):
        with pytest.raises(ValueError):
            Bar(-5)

    def test_label(self):
        bar = Bar(10, label="Loading")
        bar.update()

    def test_custom_width(self):
        bar = Bar(10, width=20)
        for _ in range(10):
            bar.update()

    # --- new tests for new behaviors ---

    def test_smooth_auto_enabled_for_full_block(self):
        bar = Bar(10)  # default fill is "█"
        assert bar.smooth is True

    def test_smooth_auto_disabled_for_other_fills(self):
        bar = Bar(10, theme="retro")  # fill is "#"
        assert bar.smooth is False

    def test_smooth_explicit_override(self):
        bar = Bar(10, smooth=False)
        assert bar.smooth is False
        bar = Bar(10, theme="retro", smooth=True)
        assert bar.smooth is True

    def test_non_tty_silent_during_progress(self):
        # writing to a StringIO (not a TTY) — should stay silent until done
        buf = io.StringIO()
        bar = Bar(10, file=buf)
        for _ in range(9):
            bar.update()
        # nothing written during progress
        assert buf.getvalue() == ""
        bar.update()  # final tick
        # final line printed without ANSI codes
        out = buf.getvalue()
        assert "\033[" not in out
        assert "100%" in out

    def test_tty_detection(self):
        buf = io.StringIO()
        bar = Bar(10, file=buf)
        assert bar._is_tty is False


# -- track() tests -----------------------------------------------------

class TestTrack:
    def test_iterates_full_range(self):
        items = list(track(range(10)))
        assert items == list(range(10))

    def test_with_label(self):
        items = list(track(range(5), label="Test"))
        assert len(items) == 5

    def test_with_theme(self):
        list(track(range(5), theme="retro"))

    def test_generator_with_total(self):
        def gen():
            for i in range(10):
                yield i
        items = list(track(gen(), total=10))
        assert len(items) == 10

    def test_generator_without_total_raises(self):
        def gen():
            yield 1
        with pytest.raises(TypeError):
            list(track(gen()))

    def test_empty_iterable(self):
        with pytest.raises(ValueError):
            list(track(range(0)))


# -- Spinner tests -----------------------------------------------------

class TestSpinner:
    def test_context_manager(self):
        with Spinner("Working..."):
            time.sleep(0.05)

    def test_manual_start_stop(self):
        sp = Spinner("Thinking...")
        sp.start()
        time.sleep(0.05)
        sp.stop()

    def test_stop_with_final_message(self):
        sp = Spinner("Loading")
        sp.start()
        time.sleep(0.05)
        sp.stop("Done!")

    def test_double_start_is_safe(self):
        sp = Spinner("Test")
        sp.start()
        sp.start()  # second call shouldn't spawn another thread
        sp.stop()

    def test_start_stop_restart(self):
        sp = Spinner("Test")
        sp.start()
        sp.stop()
        sp.start()
        sp.stop()

    def test_all_styles(self):
        styles = ["dots", "line", "circle", "bounce",
                  "arrows", "grow", "moon"]
        for style in styles:
            with Spinner("test", style=style):
                time.sleep(0.02)

    def test_named_color(self):
        with Spinner("test", color="magenta"):
            time.sleep(0.02)

    def test_hex_color(self):
        with Spinner("test", color="#00FF99"):
            time.sleep(0.02)

    def test_non_tty_no_thread_spawned(self):
        buf = io.StringIO()
        sp = Spinner("test", file=buf)
        sp.start()
        time.sleep(0.05)
        sp.stop("done")
        # no animation written, only final text
        out = buf.getvalue()
        assert "\033[" not in out
        assert "done" in out


# -- helpers ----------------------------------------------------------

class TestHelpers:
    def test_format_time_negative(self):
        assert _format_time(-1) == "--:--"

    def test_format_time_short(self):
        # sub-minute durations now show fractional seconds
        assert "s" in _format_time(0.8)
        assert "s" in _format_time(45)

    def test_format_time_minutes(self):
        assert _format_time(125) == "02:05"

    def test_format_time_hours(self):
        assert _format_time(3725) == "1:02:05"

    def test_resolve_named_color(self):
        assert resolve_color("cyan").startswith("\033[")

    def test_resolve_hex_color(self):
        result = resolve_color("#FF5733")
        assert "\033[38;2;255;87;51m" == result

    def test_resolve_invalid_hex_falls_back(self):
        result = resolve_color("#ZZZZZZ")
        assert result.startswith("\033[")

    def test_resolve_none_returns_default(self):
        assert resolve_color(None).startswith("\033[")

    def test_truncate_ansi_preserves_codes(self):
        line = "\033[94m[####]\033[0m 50%"
        result = _truncate_ansi(line, 5)
        assert "\033[94m" in result
