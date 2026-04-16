"""Tests for flashbar core functionality."""
import io
import time
import pytest
from flashbar import Bar, track, Spinner


# -- Bar --------------------------------------------------

class TestBar:
    def test_basic_creation(self):
        bar = Bar(100)
        assert bar.total == 100
        assert bar.current == 0
        assert not bar._finished

    def test_update(self):
        buf = io.StringIO()
        bar = Bar(10, file=buf)
        bar.update()
        assert bar.current == 1
        assert "%" in buf.getvalue()

    def test_update_runs_to_completion(self):
        bar = Bar(10, file=io.StringIO())
        for _ in range(10):
            bar.update()
        assert bar.current == 10
        assert bar._finished

    def test_set(self):
        bar = Bar(100, file=io.StringIO())
        bar.set(50)
        assert bar.current == 50
        bar.set(100)
        assert bar._finished

    def test_set_clamps_to_bounds(self):
        bar = Bar(10, file=io.StringIO())
        bar.set(20)
        assert bar.current == 10
        bar = Bar(10, file=io.StringIO())
        bar.set(-5)
        assert bar.current == 0

    def test_set_truncates_float(self):
        bar = Bar(100, file=io.StringIO())
        bar.set(33.7)
        assert bar.current == 33

    def test_update_past_total(self):
        bar = Bar(5, file=io.StringIO())
        for _ in range(10):
            bar.update()
        assert bar.current == 5

    def test_step_size(self):
        bar = Bar(100, file=io.StringIO())
        bar.update(step=25)
        assert bar.current == 25

    def test_context_manager(self):
        buf = io.StringIO()
        with Bar(10, file=buf) as bar:
            for _ in range(5):
                bar.update()
        assert bar._finished
        assert bar.current == 10

    def test_context_manager_on_exception(self):
        buf = io.StringIO()
        with pytest.raises(ValueError):
            with Bar(10, file=buf) as bar:
                bar.update()
                raise ValueError("boom")
        assert bar._finished

    def test_all_themes(self):
        for theme in ["default", "green", "red", "retro",
                      "minimal", "slim", "dots", "arrow"]:
            buf = io.StringIO()
            bar = Bar(5, theme=theme, file=buf)
            for _ in range(5):
                bar.update()
            assert bar._finished

    def test_named_color(self):
        buf = io.StringIO()
        bar = Bar(10, color="cyan", file=buf)
        bar.update()
        assert "\033[96m" in buf.getvalue()

    def test_hex_color(self):
        buf = io.StringIO()
        bar = Bar(10, color="#FF5733", file=buf)
        bar.update()
        assert "\033[38;2;" in buf.getvalue()

    def test_custom_fill_and_empty(self):
        buf = io.StringIO()
        bar = Bar(10, fill="▓", empty="▒", file=buf)
        bar.update()
        output = buf.getvalue()
        assert "▓" in output
        assert "▒" in output

    def test_speed_display(self):
        buf = io.StringIO()
        bar = Bar(10, show_speed=True, file=buf)
        bar.update()
        assert "it/s" in buf.getvalue()

    def test_eta_display(self):
        buf = io.StringIO()
        bar = Bar(10, show_eta=True, file=buf)
        bar.update()
        assert "ETA" in buf.getvalue()

    def test_label(self):
        buf = io.StringIO()
        bar = Bar(10, label="Loading", file=buf)
        bar.update()
        assert "Loading" in buf.getvalue()

    def test_zero_total(self):
        with pytest.raises(ValueError):
            Bar(0)

    def test_negative_total(self):
        with pytest.raises(ValueError):
            Bar(-5)


# -- track() -------------------------------------------

class TestTrack:
    def test_iterates_full_range(self):
        items = list(track(range(10), file=io.StringIO()))
        assert items == list(range(10))

    def test_with_label(self):
        items = list(track(range(5), label="Test", file=io.StringIO()))
        assert len(items) == 5

    def test_with_theme(self):
        items = list(track(range(5), theme="retro", file=io.StringIO()))
        assert len(items) == 5

    def test_generator_with_total(self):
        def gen():
            for i in range(10):
                yield i
        items = list(track(gen(), total=10, file=io.StringIO()))
        assert items == list(range(10))

    def test_generator_without_total_raises(self):
        def gen():
            yield 1
        with pytest.raises(TypeError):
            list(track(gen()))

    def test_empty_iterable(self):
        with pytest.raises(ValueError):
            list(track(range(0)))


# -- Spinner -----------------------------------------

class TestSpinner:
    def test_context_manager(self):
        buf = io.StringIO()
        with Spinner("Working...", file=buf):
            time.sleep(0.15)
        output = buf.getvalue()
        assert "✓" in output

    def test_context_manager_on_failure(self):
        buf = io.StringIO()
        with pytest.raises(RuntimeError):
            with Spinner("Nope", file=buf):
                raise RuntimeError("fail")
        assert "✗" in buf.getvalue()

    def test_manual_start_stop(self):
        buf = io.StringIO()
        sp = Spinner("Thinking...", file=buf)
        sp.start()
        time.sleep(0.15)
        sp.stop("Done!")
        assert "Done!" in buf.getvalue()

    def test_stop_clears_line(self):
        buf = io.StringIO()
        sp = Spinner("test", file=buf)
        sp.start()
        time.sleep(0.1)
        sp.stop()
        assert "\r" in buf.getvalue()

    def test_all_styles(self):
        for style in ["dots", "line", "circle", "bounce",
                      "arrows", "grow", "moon"]:
            buf = io.StringIO()
            with Spinner("test", style=style, file=buf):
                time.sleep(0.05)
            assert buf.getvalue()

    def test_color(self):
        buf = io.StringIO()
        with Spinner("test", color="#00FF99", file=buf):
            time.sleep(0.05)
        assert "\033[38;2;" in buf.getvalue()
