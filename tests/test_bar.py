"""Tests for flashbar core functionality."""
import io
import time
from unittest.mock import patch

import pytest
from flashbar import Bar, track, Spinner
from flashbar.bar import _format_time, _truncate_ansi, _visible_len, resolve_color


class TTYBuffer(io.StringIO):
    def isatty(self):
        return True


class FalseyBuffer(io.StringIO):
    def __bool__(self):
        return False


class AsciiBuffer(TTYBuffer):
    @property
    def encoding(self):
        return "ascii"

    def write(self, text):
        text.encode(self.encoding)
        return super().write(text)


class IsattyErrorBuffer(io.StringIO):
    def isatty(self):
        raise OSError("no terminal")


class BrokenBuffer:
    def isatty(self):
        return False

    def write(self, text):
        raise OSError("write failed")

    def flush(self):
        pass


class BrokenNewlineBuffer(TTYBuffer):
    def write(self, text):
        if text == "\n":
            raise OSError("newline failed")
        return super().write(text)


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

    @pytest.mark.parametrize("fill", ["ab", "界", "🙂", "\t", ""])
    def test_fill_must_be_one_terminal_cell(self, fill):
        with pytest.raises(ValueError, match="fill must occupy exactly one"):
            Bar(10, fill=fill)

    @pytest.mark.parametrize("empty", ["ab", "界", "🙂", "\t", ""])
    def test_empty_must_be_one_terminal_cell(self, empty):
        with pytest.raises(ValueError, match="empty must occupy exactly one"):
            Bar(10, empty=empty)

    def test_combining_fill_is_one_terminal_cell(self):
        bar = Bar(2, fill="e\u0301", smooth=False)
        bar.update(2)
        assert bar._finished

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

    @pytest.mark.parametrize("total", [True, 1.5, "2", float("nan"), float("inf")])
    def test_total_must_be_an_integer(self, total):
        with pytest.raises(TypeError, match="total must be an integer"):
            Bar(total)

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

    def test_isatty_error_falls_back_to_non_tty(self):
        bar = Bar(1, file=IsattyErrorBuffer())
        assert bar._is_tty is False
        bar.update()

    @pytest.mark.parametrize("width", [0, -1, -100])
    def test_width_must_be_positive(self, width):
        with pytest.raises(ValueError, match="width must be > 0"):
            Bar(10, width=width)

    def test_width_must_be_an_integer(self):
        for width in (2.5, True, "2"):
            with pytest.raises(TypeError, match="width must be an integer"):
                Bar(10, width=width)

    def test_negative_update_is_rejected(self):
        bar = Bar(10)
        with pytest.raises(ValueError, match="step must be >= 0"):
            bar.update(-1)
        assert bar.current == 0

    @pytest.mark.parametrize("step", [True, 0.5, "1", None])
    def test_update_step_must_be_an_integer(self, step):
        bar = Bar(10)
        with pytest.raises(TypeError, match="step must be an integer"):
            bar.update(step)
        assert bar.current == 0

    def test_negative_update_is_rejected_after_finish(self):
        bar = Bar(1)
        bar.update()
        with pytest.raises(ValueError, match="step must be >= 0"):
            bar.update(-1)

    def test_context_output_error_does_not_mask_user_error(self):
        bar = Bar(2, file=BrokenBuffer())
        with pytest.raises(ValueError, match="user failure"):
            with bar:
                raise ValueError("user failure")
        assert bar._finished

    def test_context_output_error_propagates_without_user_error(self):
        bar = Bar(2, file=BrokenBuffer())
        with pytest.raises(OSError, match="write failed"):
            with bar:
                pass
        assert bar._finished

    def test_multiline_label_is_rendered_on_one_line(self):
        buf = io.StringIO()
        bar = Bar(1, label="first\r\nsecond", width=2, file=buf)
        bar.update()
        assert "first  second" in buf.getvalue()

    def test_open_hyperlink_in_label_is_closed_before_the_bar(self):
        buf = TTYBuffer()
        label = "\x1b]8;;https://example.com\x1b\\link"
        bar = Bar(2, label=label, width=2, file=buf)
        bar.update()

        assert "link\x1b]8;;\x1b\\ \x1b[" in buf.getvalue()

    def test_set_reopens_a_finished_bar(self):
        bar = Bar(2, file=io.StringIO())
        bar.set(2)
        assert bar._finished

        bar.set(1)
        assert not bar._finished
        bar.update()
        assert bar.current == 2
        assert bar._finished

    def test_reopening_a_finished_bar_restarts_the_timer(self):
        buf = io.StringIO()
        with patch("flashbar.bar.time.monotonic") as clock:
            clock.return_value = 1.0
            bar = Bar(2, width=2, file=buf)
            clock.return_value = 2.0
            bar.set(2)
            clock.return_value = 10.0
            bar.set(1)
            clock.return_value = 12.0
            bar.update()

        assert " 2.0s" in buf.getvalue().splitlines()[-1]

    def test_repeated_set_at_total_is_a_noop(self):
        buf = io.StringIO()
        bar = Bar(2, file=buf)
        bar.set(2)
        first_output = buf.getvalue()
        bar.set(2)
        assert buf.getvalue() == first_output

    def test_set_bypasses_redraw_throttle(self):
        buf = TTYBuffer()
        with patch("flashbar.bar.time.monotonic", return_value=10.0):
            bar = Bar(10, width=4, file=buf)
            bar.update()
            first_draw = len(buf.getvalue())
            bar.set(5)

        second_draw = buf.getvalue()[first_draw:]
        assert " 50%" in second_draw

    def test_timer_starts_before_first_manual_step(self):
        buf = io.StringIO()
        with patch("flashbar.bar.time.monotonic") as clock:
            clock.return_value = 10.0
            bar = Bar(1, width=2, file=buf)
            clock.return_value = 12.5
            bar.update()

        assert " 2.5s" in buf.getvalue()

    def test_context_timer_includes_body_before_any_update(self):
        buf = io.StringIO()
        with patch("flashbar.bar.time.monotonic") as clock:
            clock.return_value = 1.0
            bar = Bar(1, width=2, file=buf)
            clock.return_value = 5.0
            with bar:
                clock.return_value = 8.0

        assert " 3.0s" in buf.getvalue()

    def test_falsey_file_is_not_replaced_with_stderr(self):
        buf = FalseyBuffer()
        bar = Bar(1, file=buf)
        assert bar.file is buf
        bar.update()
        assert "100%" in buf.getvalue()

    def test_legacy_encoded_stream_replaces_unsupported_glyphs(self):
        buf = AsciiBuffer()
        bar = Bar(1, label="café", file=buf)
        bar.update()
        assert "100%" in buf.getvalue()
        buf.getvalue().encode("ascii")

    def test_huge_total_does_not_round_up_or_overflow(self):
        buf = TTYBuffer()
        huge = 10 ** 10000
        with patch("flashbar.bar.time.monotonic") as clock:
            clock.return_value = 1.0
            bar = Bar(huge, width=2, file=buf, show_speed=True)
            clock.return_value = 2.0
            bar.set(1)
            bar.set(huge - 1)

        output = buf.getvalue()
        assert "ETA --:--" in output
        assert " 99%" in output
        assert "inf it/s" in output
        assert not bar._finished

    def test_custom_unit_shows_count_and_rate(self):
        buf = io.StringIO()
        with patch("flashbar.bar.time.monotonic") as clock:
            clock.return_value = 0.0
            bar = Bar(
                2048, file=buf, unit="B", unit_scale=True, show_speed=True
            )
            clock.return_value = 2.0
            bar.update(2048)

        output = buf.getvalue()
        assert "2.0 KiB / 2.0 KiB" in output
        assert "1.0 KiB/s" in output

    def test_non_byte_units_use_decimal_scaling(self):
        buf = io.StringIO()
        Bar(2000, file=buf, unit="row", unit_scale=True).update(2000)
        assert "2.0 krow / 2.0 krow" in buf.getvalue()

    def test_decimal_scale_carries_after_rounding(self):
        buf = io.StringIO()
        Bar(999_999, file=buf, unit="row", unit_scale=True).update(999_999)
        assert "1.0 Mrow / 1.0 Mrow" in buf.getvalue()

    @pytest.mark.parametrize(
        ("total", "expected"),
        [
            (1023, "1023 B / 1023 B"),
            (1024, "1.0 KiB / 1.0 KiB"),
            (1024 ** 2, "1.0 MiB / 1.0 MiB"),
        ],
    )
    def test_byte_scale_boundaries(self, total, expected):
        buf = io.StringIO()
        Bar(total, file=buf, unit="B", unit_scale=True).update(total)
        assert expected in buf.getvalue()

    def test_byte_scale_carries_after_rounding(self):
        buf = io.StringIO()
        almost_mib = 1024 ** 2 - 1
        Bar(almost_mib, file=buf, unit="B", unit_scale=True).update(almost_mib)
        assert "1.0 MiB / 1.0 MiB" in buf.getvalue()

    def test_unscaled_unit_keeps_integer_counts(self):
        buf = io.StringIO()
        Bar(2, file=buf, unit="files").update(2)
        assert "2 / 2 files" in buf.getvalue()

    def test_default_unit_preserves_legacy_output(self):
        buf = io.StringIO()
        Bar(2, file=buf).update(2)
        assert "2 / 2" not in buf.getvalue()

    @pytest.mark.parametrize("unit", [1, True, object()])
    def test_unit_must_be_a_string(self, unit):
        with pytest.raises(TypeError, match="unit must be a string"):
            Bar(2, unit=unit)

    @pytest.mark.parametrize("value", [1, 0, "yes", None])
    def test_unit_scale_must_be_boolean(self, value):
        with pytest.raises(TypeError, match="unit_scale must be a boolean"):
            Bar(2, unit_scale=value)

    def test_scaled_huge_value_does_not_overflow(self):
        buf = io.StringIO()
        huge = 10 ** 10000
        bar = Bar(huge, width=2, file=buf, unit="B", unit_scale=True)
        bar.update(huge)
        assert bar._finished
        assert "100%" in buf.getvalue()

    def test_unscaled_huge_value_does_not_overflow(self):
        buf = io.StringIO()
        huge = 10 ** 10000
        bar = Bar(huge, width=2, file=buf, unit="items")
        bar.update(huge)
        assert bar._finished
        assert "1.0e+10000 / 1.0e+10000 items" in buf.getvalue()

    def test_set_label_and_postfix_redraw_immediately(self):
        buf = TTYBuffer()
        bar = Bar(3, width=3, file=buf)
        bar.set_label("phase\n2")
        first = len(buf.getvalue())
        bar.set_postfix(files=1, errors=0)

        assert "phase 2" in buf.getvalue()
        assert "files=1 errors=0" in buf.getvalue()[first:]

    def test_set_postfix_replaces_and_empty_call_clears(self):
        buf = TTYBuffer()
        bar = Bar(3, width=3, file=buf)
        bar.set_postfix(first=1)
        before_replace = len(buf.getvalue())
        bar.set_postfix(second=2)
        replaced = buf.getvalue()[before_replace:]
        assert "first=1" not in replaced
        assert "second=2" in replaced

        before_clear = len(buf.getvalue())
        bar.set_postfix()
        assert "second=2" not in buf.getvalue()[before_clear:]

    def test_postfix_closes_ansi_between_fields(self):
        buf = TTYBuffer()
        bar = Bar(2, width=2, file=buf)
        bar.set_postfix(a="\033[31mred", b="plain")
        assert "a=\033[31mred\033[0m b=plain" in buf.getvalue()

    def test_postfix_closes_hyperlink_between_fields(self):
        buf = TTYBuffer()
        bar = Bar(2, width=2, file=buf)
        bar.set_postfix(a="\033]8;;https://example.com\033\\link", b="plain")
        close = "\033]8;;\033\\"
        assert f"link{close} b=plain" in buf.getvalue()

    def test_dynamic_fields_do_not_redraw_finished_bar(self):
        buf = io.StringIO()
        bar = Bar(1, file=buf)
        bar.update()
        output = buf.getvalue()
        bar.set_label("later")
        bar.set_postfix(done=True)
        assert buf.getvalue() == output

    def test_postfix_is_rendered_after_statistics(self):
        buf = io.StringIO()
        bar = Bar(1, file=buf)
        bar.set_postfix(files=1)
        bar.update()
        assert buf.getvalue().rstrip().endswith("files=1")

    def test_non_tty_strips_ansi_from_dynamic_text(self):
        buf = io.StringIO()
        bar = Bar(1, label="\033[31mred\033[0m", file=buf, unit="\033[32mB")
        bar.set_postfix(state="\033[33mok\033[0m")
        bar.update()
        assert "\033[" not in buf.getvalue()
        assert "red" in buf.getvalue()
        assert "state=ok" in buf.getvalue()

    def test_transient_erases_completed_tty_line(self):
        buf = TTYBuffer()
        Bar(1, width=2, file=buf, transient=True).update()
        assert buf.getvalue().endswith("\r\033[2K")
        assert not buf.getvalue().endswith("\n")

    def test_transient_suppresses_non_tty_summary(self):
        buf = io.StringIO()
        Bar(1, file=buf, transient=True).update()
        assert buf.getvalue() == ""

    @pytest.mark.parametrize("value", [1, 0, "yes", None])
    def test_transient_must_be_boolean(self, value):
        with pytest.raises(TypeError, match="transient must be a boolean"):
            Bar(1, transient=value)

    def test_transient_context_preserves_user_exception(self):
        buf = TTYBuffer()
        with pytest.raises(RuntimeError, match="task failed"):
            with Bar(2, file=buf, transient=True):
                raise RuntimeError("task failed")
        assert buf.getvalue().endswith("\r\033[2K")

    def test_indeterminate_bar_updates_without_percent_or_eta(self):
        buf = TTYBuffer()
        bar = Bar(None, width=5, file=buf, show_eta=True)
        bar.set(1)
        bar.set(2)

        output = buf.getvalue()
        assert "░███░" in output
        assert "░░███" in output
        assert "%" not in output
        assert "ETA" not in output
        assert "2 it" in output
        assert bar.current == 2
        assert not bar._finished

    def test_indeterminate_set_clamps_negative_value(self):
        bar = Bar(None, file=io.StringIO())
        bar.set(-10)
        assert bar.current == 0
        assert not bar._finished

    def test_set_total_switches_to_determinate_mode(self):
        buf = TTYBuffer()
        bar = Bar(None, width=5, file=buf)
        bar.set(3)
        before = len(buf.getvalue())
        bar.set_total(10)

        assert bar.total == 10
        assert bar.current == 3
        assert not bar._finished
        assert " 30%" in buf.getvalue()[before:]

    def test_set_total_clamps_and_completes(self):
        buf = io.StringIO()
        bar = Bar(None, width=2, file=buf)
        bar.update(5)
        bar.set_total(3)
        assert bar.current == 3
        assert bar._finished
        assert "100%" in buf.getvalue()

    @pytest.mark.parametrize("total", [None, True, 1.5, "2"])
    def test_set_total_requires_an_integer(self, total):
        with pytest.raises(TypeError, match="total must be an integer"):
            Bar(None).set_total(total)

    @pytest.mark.parametrize("total", [0, -1])
    def test_set_total_must_be_positive(self, total):
        with pytest.raises(ValueError, match="total must be > 0"):
            Bar(None).set_total(total)

    def test_larger_total_reopens_finished_bar(self):
        buf = io.StringIO()
        bar = Bar(2, file=buf)
        bar.update(2)
        bar.set_total(4)
        assert bar.current == 2
        assert bar.total == 4
        assert not bar._finished

    def test_reopened_total_restarts_timer(self):
        buf = io.StringIO()
        with patch("flashbar.bar.time.monotonic") as clock:
            clock.return_value = 1.0
            bar = Bar(2, file=buf)
            clock.return_value = 3.0
            bar.update(2)
            clock.return_value = 10.0
            bar.set_total(4)
            clock.return_value = 12.0
            bar.update(2)

        assert " 2.0s" in buf.getvalue().splitlines()[-1]

    def test_smaller_total_finishes_active_bar(self):
        buf = io.StringIO()
        bar = Bar(10, file=buf)
        bar.set(6)
        bar.set_total(5)
        assert bar.total == 5
        assert bar.current == 5
        assert bar._finished
        assert "100%" in buf.getvalue()

    def test_smaller_total_redraws_finished_output(self):
        buf = io.StringIO()
        bar = Bar(4, file=buf, unit="items")
        bar.update(4)
        bar.set_total(2)
        assert bar.total == 2
        assert bar.current == 2
        assert bar._finished
        assert len(buf.getvalue().splitlines()) == 2
        assert "2 / 2 items" in buf.getvalue().splitlines()[-1]

    def test_same_total_is_a_noop(self):
        buf = TTYBuffer()
        bar = Bar(3, file=buf)
        bar.update()
        output = buf.getvalue()
        bar.set_total(3)
        assert buf.getvalue() == output

    def test_indeterminate_context_prints_clean_summary(self):
        buf = io.StringIO()
        with Bar(None, width=2, file=buf) as bar:
            bar.update(3)

        output = buf.getvalue()
        assert bar._finished
        assert "3 it" in output
        assert "%" not in output
        assert "ETA" not in output
        assert "s" in output


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

    def test_unit_options_are_forwarded(self):
        buf = io.StringIO()
        list(track(range(1024), file=buf, unit="B", unit_scale=True))
        assert "1.0 KiB / 1.0 KiB" in buf.getvalue()

    def test_transient_track_erases_completed_tty_line(self):
        buf = TTYBuffer()
        list(track(range(2), width=2, file=buf, transient=True))
        assert buf.getvalue().endswith("\r\033[2K")

    def test_transient_track_erases_line_when_closed_early(self):
        buf = TTYBuffer()
        iterator = track(range(4), width=2, file=buf, transient=True)
        assert next(iterator) == 0
        assert next(iterator) == 1
        iterator.close()
        assert buf.getvalue().endswith("\r\033[2K")
        assert "100%" not in buf.getvalue()

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

    def test_timer_includes_work_on_the_first_item(self):
        buf = io.StringIO()
        with patch("flashbar.bar.time.monotonic") as clock:
            clock.return_value = 20.0
            iterator = track(["item"], width=2, file=buf)
            assert next(iterator) == "item"
            clock.return_value = 24.0
            with pytest.raises(StopIteration):
                next(iterator)

        assert " 4.0s" in buf.getvalue()

    def test_close_terminates_an_open_tty_line(self):
        buf = TTYBuffer()
        iterator = track(range(5), width=2, file=buf)
        assert next(iterator) == 0
        assert next(iterator) == 1
        assert not buf.getvalue().endswith("\n")

        iterator.close()
        assert buf.getvalue().endswith("\n")
        assert "100%" not in buf.getvalue()

    def test_break_terminates_tty_line(self):
        buf = TTYBuffer()
        for item in track(range(5), width=2, file=buf):
            if item == 1:
                break

        assert buf.getvalue().endswith("\n")
        assert "100%" not in buf.getvalue()

    def test_iterable_exception_terminates_tty_line(self):
        def broken():
            yield 1
            raise RuntimeError("broken iterable")

        buf = TTYBuffer()
        iterator = track(broken(), total=3, width=2, file=buf)
        assert next(iterator) == 1
        with pytest.raises(RuntimeError, match="broken iterable"):
            next(iterator)

        assert buf.getvalue().endswith("\n")
        assert "100%" not in buf.getvalue()

    def test_cleanup_error_does_not_mask_iterable_exception(self):
        def broken():
            yield 1
            raise RuntimeError("broken iterable")

        iterator = track(
            broken(), total=3, width=2, file=BrokenNewlineBuffer()
        )
        assert next(iterator) == 1
        with pytest.raises(RuntimeError, match="broken iterable"):
            next(iterator)

    def test_track_rejects_unknown_bar_options(self):
        with pytest.raises(TypeError):
            track([1], widht=2)


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

    @pytest.mark.parametrize(
        ("text", "cells"),
        [
            ("界", 2),
            ("e\u0301", 1),
            ("🙂", 2),
            ("👩\u200d💻", 2),
            ("🇺🇦", 2),
            ("❤️", 2),
            ("a\tb", 9),
            ("\033[31m界\033[0m", 2),
        ],
    )
    def test_visible_len_uses_terminal_cells(self, text, cells):
        assert _visible_len(text) == cells

    def test_truncate_keeps_combining_cluster_intact(self):
        result = _truncate_ansi("e\u0301x", 1)
        assert result == "e\u0301"
        assert _visible_len(result) == 1

    def test_truncate_does_not_split_wide_or_emoji_clusters(self):
        assert _truncate_ansi("界x", 1) == ""
        assert _truncate_ansi("👩\u200d💻x", 2) == "👩\u200d💻"

    def test_plain_truncation_does_not_add_reset(self):
        assert _truncate_ansi("abcdef", 3) == "abc"

    def test_colored_truncation_closes_active_sgr(self):
        result = _truncate_ansi("\033[31m界🙂x\033[0m", 4)
        assert result == "\033[31m界🙂\033[0m"
        assert _visible_len(result) == 4

    def test_truncate_keeps_ansi_escape_whole(self):
        result = _truncate_ansi("\033[38;2;10;20;30mhello\033[0m", 2)
        assert "\033[38;2;10;20;30m" in result
        assert "\033[38;2" not in result.replace("\033[38;2;10;20;30m", "")
        assert result.endswith("\033[0m")

    def test_truncate_respects_tab_stops(self):
        result = _truncate_ansi("a\tb", 8)
        assert result == "a\t"
        assert _visible_len(result) == 8

    def test_format_time_handles_non_finite_values(self):
        assert _format_time(float("inf")) == "--:--"
        assert _format_time(float("nan")) == "--:--"
