"""Tests for flashbar core functionality."""
import time
import pytest
from flashbar import Bar, track, Spinner


# -- Bar tests ---------------------------------------------------------

class TestBar:
    def test_basic_creation(self):
        bar = Bar(100)
        assert bar is not None

    def test_update_runs_to_completion(self):
        bar = Bar(10)
        for _ in range(10):
            bar.update()

    def test_set_jumps_to_value(self):
        bar = Bar(100)
        bar.set(50)
        bar.set(100)

    def test_set_beyond_total_no_crash(self):
        # edge case: user passes value bigger than total
        bar = Bar(10)
        bar.set(20)

    def test_update_past_total_no_crash(self):
        bar = Bar(5)
        for _ in range(10):
            bar.update()

    def test_context_manager(self):
        with Bar(10) as bar:
            for _ in range(10):
                bar.update()

    def test_context_manager_handles_exception(self):
        # bar should clean up even if something blows up inside
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
        # Bar correctly rejects zero total
        with pytest.raises(ValueError):
            Bar(0)

    def test_negative_total(self):
        # negative total should also be rejected
        with pytest.raises(ValueError):
            Bar(-5)

    def test_label(self):
        bar = Bar(10, label="Loading")
        bar.update()

    def test_custom_width(self):
        bar = Bar(10, width=20)
        for _ in range(10):
            bar.update()


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
        # generators don't have len(), so total= is required
        def gen():
            for i in range(10):
                yield i
        items = list(track(gen(), total=10))
        assert len(items) == 10

    def test_empty_iterable(self):
        # track() on empty range raises ValueError since total=0
        with pytest.raises(ValueError):
            list(track(range(0)))


# -- Spinner tests -----------------------------------------------------

class TestSpinner:
    def test_context_manager(self):
        with Spinner("Working..."):
            time.sleep(0.1)

    def test_manual_start_stop(self):
        sp = Spinner("Thinking...")
        sp.start()
        time.sleep(0.1)
        sp.stop()

    def test_stop_with_final_message(self):
        sp = Spinner("Loading")
        sp.start()
        time.sleep(0.1)
        sp.stop("Done!")

    def test_all_styles(self):
        styles = ["dots", "line", "circle", "bounce",
                  "arrows", "grow", "moon"]
        for style in styles:
            with Spinner("test", style=style):
                time.sleep(0.05)

    def test_named_color(self):
        with Spinner("test", color="magenta"):
            time.sleep(0.05)

    def test_hex_color(self):
        with Spinner("test", color="#00FF99"):
            time.sleep(0.05)
