import io
import re

import pytest

from flashbar import error, info, panel, print_panel, rule, success, warn
from flashbar.bar import _visible_len

ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x1b\x07]*(?:\x07|\x1b\\))")
OPEN_LINK = "\x1b]8;;https://example.com\x1b\\"
CLOSE_LINK = "\x1b]8;;\x1b\\"


def strip_ansi(text):
    return ANSI_RE.sub("", text)


class TTYBuffer(io.StringIO):
    def isatty(self):
        return True


class FalsyBuffer(io.StringIO):
    def __bool__(self):
        return False


class LegacyTTY(TTYBuffer):
    @property
    def encoding(self):
        return "ascii"


class IsattyErrorBuffer(io.StringIO):
    def isatty(self):
        raise OSError("no terminal")


class WriteTimeLegacy(TTYBuffer):
    @property
    def encoding(self):
        return None

    def write(self, text):
        text.encode("ascii")
        return super().write(text)


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
        out = panel("x", style="rounded", plain=False)
        assert "╭" in out and "╯" in out

    def test_panel_ascii_chars(self):
        out = panel("x", style="ascii")
        assert "+" in out
        assert "─" not in out  # no fancy chars

    def test_panel_color_named(self):
        out = panel("x", color="green", plain=False)
        assert "\033[" in out  # has ANSI codes

    def test_panel_color_hex(self):
        out = panel("x", color="#FF5733", plain=False)
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

    def test_wide_unicode_uses_terminal_cells(self):
        out = panel("界", title="标题", width=12)
        assert all(_visible_len(line) == 12 for line in out.splitlines())

    def test_combining_character_does_not_consume_a_cell(self):
        out = panel("e\u0301", width=8)
        assert all(_visible_len(line) == 8 for line in out.splitlines())

    def test_tabs_are_expanded_inside_fixed_width(self):
        out = panel("a\tb", width=14, padding=1)
        assert "\t" not in out
        assert all(_visible_len(line) == 14 for line in out.splitlines())

    def test_ansi_title_is_truncated_without_broken_escape(self):
        out = panel(
            "body", title="\033[31m" + "界" * 20, width=14, plain=False
        )
        top = out.splitlines()[0]
        assert _visible_len(top) == 14
        assert "\x1b" not in ANSI_RE.sub("", top)

    def test_body_style_is_reset_before_right_padding(self):
        body = panel("\033[31mred", width=12, plain=False).splitlines()[1]
        assert "red\033[0m" in body
        assert body.endswith("│")

    def test_open_hyperlink_is_closed_before_padding(self):
        body = panel(
            OPEN_LINK + "click", width=14, plain=False
        ).splitlines()[1]
        assert "click" + CLOSE_LINK in body

    def test_crlf_and_lone_cr_are_normalised(self):
        out = panel("one\r\ntwo\rthree", width=12)
        assert "\r" not in out
        assert len(out.splitlines()) == 5

    @pytest.mark.parametrize(
        "kwargs, error_type",
        [
            ({"padding": -1}, ValueError),
            ({"padding": 1.5}, TypeError),
            ({"width": 3, "padding": 1}, ValueError),
            ({"width": 2, "padding": 0, "title": "x"}, ValueError),
            ({"width": 10.5}, TypeError),
        ],
    )
    def test_invalid_geometry_is_rejected(self, kwargs, error_type):
        with pytest.raises(error_type):
            panel("x", **kwargs)

    def test_plain_panel_strips_nested_ansi_and_reset(self):
        out = panel("\033[31mred", title="\033[1mTitle", width=14, plain=True)
        assert "\033" not in out
        assert out.startswith("+")

    def test_plain_truncation_does_not_add_reset(self):
        out = panel("x" * 100, width=12, style="ascii")
        assert "\033" not in out


# -- rule() -----------------------------------------------

class TestRule:
    def test_plain_rule(self):
        out = rule(width=20, plain=False)
        assert "─" in out
        assert _visible_len(out) == 20

    def test_rule_with_label(self):
        out = rule("Section", width=30, plain=False)
        assert "Section" in strip_ansi(out)
        assert _visible_len(out) == 30

    def test_rule_label_too_long(self):
        out = rule("X" * 50, width=10, plain=False)
        assert strip_ansi(out) == "X" * 10
        assert _visible_len(out) == 10

    def test_rule_color(self):
        out = rule(width=10, color="red", plain=False)
        assert "\033[91m" in out

    def test_wide_long_label_keeps_width_contract(self):
        out = rule("界" * 8, width=9, plain=False)
        assert _visible_len(out) == 9

    def test_ansi_label_is_not_cut_mid_sequence(self):
        out = rule("\033[31m" + "label" * 10, width=9, plain=False)
        assert _visible_len(out) == 9
        assert "\x1b" not in ANSI_RE.sub("", out)

    def test_plain_rule_has_no_ansi_or_unicode_decoration(self):
        out = rule("\033[31mSection", width=20, plain=True)
        assert "\033" not in out
        assert "─" not in out
        assert _visible_len(out) == 20

    def test_open_hyperlink_is_closed_in_rule_label(self):
        out = rule(OPEN_LINK + "Docs", width=16, plain=False)
        assert "Docs" + CLOSE_LINK in out

    @pytest.mark.parametrize("width", [0, -3, 2.5, True])
    def test_rule_rejects_invalid_width(self, width):
        with pytest.raises((TypeError, ValueError)):
            rule(width=width)


# -- status indicators ------------------------------------

class TestIndicators:
    def test_success_has_check(self):
        out = success("done", plain=False)
        assert "✓" in out
        assert "done" in strip_ansi(out)

    def test_error_has_x(self):
        out = error("failed", plain=False)
        assert "✗" in out

    def test_warn_has_sign(self):
        out = warn("careful", plain=False)
        assert "⚠" in out

    def test_info_has_i(self):
        out = info("note", plain=False)
        assert "ℹ" in out

    def test_indicators_have_colors(self):
        for fn in [success, error, warn, info]:
            out = fn("msg", plain=False)
            assert "\033[" in out  # ANSI present

    @pytest.mark.parametrize(
        "fn, prefix",
        [(success, "[OK]"), (error, "[x]"), (warn, "[!]"), (info, "[i]")],
    )
    def test_plain_indicators_are_ascii_and_strip_nested_ansi(self, fn, prefix):
        out = fn("\033[31mmessage", plain=True)
        assert out.startswith(prefix)
        assert "\033" not in out

    def test_message_style_cannot_leak(self):
        out = success("\033[1mbold", plain=False)
        assert out.endswith("\033[0m")

    def test_open_hyperlink_is_closed_in_status_message(self):
        out = success(OPEN_LINK + "Docs", plain=False)
        assert out.endswith("Docs" + CLOSE_LINK)

    def test_non_tty_defaults_to_plain(self, monkeypatch):
        monkeypatch.setattr("flashbar.pretty.sys.stdout", io.StringIO())
        assert success("done") == "[OK] done"
        assert "\033" not in rule("Log", width=12)
        assert panel("body", width=10).startswith("+")

    def test_tty_defaults_to_styled(self, monkeypatch):
        monkeypatch.setattr("flashbar.pretty.sys.stdout", TTYBuffer())
        assert "\033" in success("done")
        assert "─" in rule(width=12)
        assert panel("body", width=10).startswith("╭")

    def test_legacy_tty_defaults_to_ascii(self, monkeypatch):
        monkeypatch.setattr("flashbar.pretty.sys.stdout", LegacyTTY())
        assert success("done") == "[OK] done"
        assert rule(width=8) == "-" * 8
        rendered = panel("body", title="Title", width=12)
        assert rendered.startswith("+- Title")
        rendered.encode("ascii")

    def test_legacy_tty_replaces_unencodable_user_text(self, monkeypatch):
        monkeypatch.setattr("flashbar.pretty.sys.stdout", LegacyTTY())
        rendered = panel("界🙂", title="标题", width=12)
        rendered.encode("ascii")
        assert "?" in rendered
        assert success("界").encode("ascii")
        assert rule("界", width=8).encode("ascii")


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

    def test_non_tty_strips_ansi_from_title_and_body(self):
        buf = io.StringIO()
        print_panel("\033[31mbody", title="\033[1mTitle", file=buf)
        assert buf.getvalue() == "[Title] body\n"

    def test_non_tty_still_validates_panel_kwargs(self):
        with pytest.raises(TypeError):
            print_panel("body", file=io.StringIO(), widht=20)

    def test_falsey_file_is_not_replaced_with_stdout(self):
        buf = FalsyBuffer()
        print_panel("body", file=buf)
        assert buf.getvalue() == "body\n"

    def test_explicit_plain_mode_keeps_ascii_panel_for_non_tty(self):
        buf = io.StringIO()
        print_panel("body", title="Title", width=14, plain=True, file=buf)
        output = buf.getvalue()
        assert output.startswith("+- Title")
        assert output.endswith("+\n")

    def test_isatty_error_uses_clean_non_tty_output(self):
        buf = IsattyErrorBuffer()
        print_panel("body", title="Title", file=buf)
        assert buf.getvalue() == "[Title] body\n"

    def test_legacy_encoding_gets_ascii_border_fallback(self):
        buf = LegacyTTY()
        print_panel("body", title="Title", width=16, file=buf)
        output = buf.getvalue()
        assert output.startswith("+- Title ")
        output.encode("ascii")

    def test_write_time_encoding_error_gets_ascii_fallback(self):
        buf = WriteTimeLegacy()
        print_panel("body", title="Title", width=16, file=buf)
        output = buf.getvalue()
        assert output.startswith("+- Title ")
        output.encode("ascii")

    def test_tty_uses_full_panel(self):
        buf = TTYBuffer()
        print_panel("body", width=12, file=buf)
        assert buf.getvalue().startswith("╭")
