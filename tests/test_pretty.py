"""Tests for the pretty output module."""
import io
import re
import pytest

from flashbar import panel, rule, success, error, warn, info, print_panel
from flashbar.bar import _visible_len

ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def strip_ansi(text):
    return ANSI_RE.sub("", text)


# -- panel() ----------------------------------------------

class TestPanel:
    def test_basic_panel(self):
        out = panel("hello")
        assert "hello" in strip_ansi(out)
        # has top, body, bottom — at least 3 lines
        assert len(out.split("\n")) >= 3

    def test_panel_with_title(self):
        out = panel("body", title="Greeting")
        assert "Greeting" in strip_ansi(out)
        assert "body" in strip_ansi(out)

    def test_panel_multiline(self):
        out = panel("line1\nline2\nline3")
        clean = strip_ansi(out)
        assert "line1" in clean
        assert "line2" in clean
        assert "line3" in clean

    def test_panel_styles(self):
        for style in ["rounded", "square", "double", "heavy", "ascii"]:
            out = panel("x", style=style)
            assert "x" in strip_ansi(out)

    def test_panel_unknown_style_falls_back(self):
        # bad style shouldn't crash
        out = panel("x", style="nonexistent")
        assert "x" in strip_ansi(out)

    def test_panel_rounded_chars(self):
        out = panel("x", style="rounded")
        assert "╭" in out and "╯" in out

    def test_panel_ascii_chars(self):
        out = panel("x", style="ascii")
        assert "+" in out
        assert "─" not in out  # no fancy chars

    def test_panel_color_named(self):
        out = panel("x", color="green")
        assert "\033[" in out  # has ANSI codes

    def test_panel_color_hex(self):
        out = panel("x", color="#FF5733")
        assert "\033[38;2;255;87;51m" in out

    def test_panel_no_color(self):
        out = panel("x")
        # no ANSI codes when no color requested
        assert "\033[" not in out

    def test_panel_explicit_width(self):
        out = panel("x", width=30, color=None)
        # check first line (top border) is exactly 30 visible chars
        first_line = out.split("\n")[0]
        assert _visible_len(first_line) == 30

    def test_panel_truncates_long_line(self):
        # very long line should fit inside the panel
        out = panel("x" * 200, width=30)
        for line in out.split("\n"):
            assert _visible_len(line) <= 30

    def test_panel_padding(self):
        out = panel("x", width=20, padding=2)
        # body line should have 2 spaces around content
        body = strip_ansi(out.split("\n")[1])
        assert "  x  " in body


# -- rule() -----------------------------------------------

class TestRule:
    def test_plain_rule(self):
        out = rule(width=20)
        assert "─" in out
        assert _visible_len(out) == 20

    def test_rule_with_label(self):
        out = rule("Section", width=30)
        assert "Section" in strip_ansi(out)
        assert _visible_len(out) == 30

    def test_rule_label_too_long(self):
        # if label is longer than width, just show the label
        out = rule("X" * 50, width=10)
        assert "X" in strip_ansi(out)

    def test_rule_color(self):
        out = rule(width=10, color="red")
        assert "\033[91m" in out


# -- status indicators ------------------------------------

class TestIndicators:
    def test_success_has_check(self):
        out = success("done")
        assert "✓" in out
        assert "done" in strip_ansi(out)

    def test_error_has_x(self):
        out = error("failed")
        assert "✗" in out

    def test_warn_has_sign(self):
        out = warn("careful")
        assert "⚠" in out

    def test_info_has_i(self):
        out = info("note")
        assert "ℹ" in out

    def test_indicators_have_colors(self):
        for fn in [success, error, warn, info]:
            out = fn("msg")
            assert "\033[" in out  # ANSI present


# -- print_panel ------------------------------------------

class TestPrintPanel:
    def test_print_panel_to_buffer(self):
        buf = io.StringIO()
        print_panel("hi", file=buf)
        # StringIO is non-TTY → strips styling
        out = buf.getvalue()
        assert "hi" in out
        assert "\033[" not in out

    def test_print_panel_with_title_non_tty(self):
        buf = io.StringIO()
        print_panel("body", title="Title", file=buf)
        out = buf.getvalue()
        # non-TTY: title shown as bracket prefix
        assert "[Title]" in out
        assert "body" in out
