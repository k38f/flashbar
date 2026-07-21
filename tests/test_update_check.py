from __future__ import annotations

import importlib
import io
import json
import sys
import time
import urllib.error
from pathlib import Path
from unittest import mock

import pytest
from packaging.version import Version

from flashbar import Bar, Spinner
from flashbar import update_check


bar_module = importlib.import_module("flashbar.bar")
spinner_module = importlib.import_module("flashbar.spinner")


class TTYStream(io.StringIO):
    def isatty(self):
        return True


class EncodedTTY(io.TextIOWrapper):
    def isatty(self):
        return True


@pytest.fixture(autouse=True)
def clean_update_environment(monkeypatch):
    for name in (
        "FLASHBAR_NO_UPDATE_CHECK",
        "CI",
        "GITHUB_ACTIONS",
        "XDG_CACHE_HOME",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "argv", ["flashbar-test"])
    monkeypatch.setattr(update_check, "_automatic_attempted", False)


@pytest.fixture
def fake_cache(tmp_path, monkeypatch):
    path = tmp_path / "flashbar" / "update-check.json"
    monkeypatch.setattr(update_check, "_cache_path", lambda: path)
    return path


def _write_cache(path: Path, **values) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values), encoding="utf-8")


def test_check_interval_is_one_week():
    assert update_check.CHECK_INTERVAL == 7 * 24 * 60 * 60


@pytest.mark.parametrize(
    ("latest", "current", "expected"),
    [
        ("1.10", "1.9", True),
        ("1.0", "1.0rc1", True),
        ("1.0.post1", "1.0", True),
        ("2!0.1", "1!99", True),
        ("1.0rc1", "1.0", False),
        ("1.0", "1.0", False),
        ("broken", "1.0", False),
    ],
)
def test_pep440_version_ordering(latest, current, expected):
    assert update_check._is_newer(latest, current) is expected


def test_recent_cache_skips_pypi(fake_cache):
    _write_cache(
        fake_cache,
        checked_at=time.time() - 60,
        latest_version="1.4.0",
    )

    with mock.patch.object(update_check, "_fetch_latest_version") as fetch:
        assert update_check.check("1.3.0") == "1.4.0"
    fetch.assert_not_called()


def test_cache_at_weekly_boundary_is_refreshed(fake_cache, monkeypatch):
    now = 50_000.0
    _write_cache(
        fake_cache,
        checked_at=now - update_check.CHECK_INTERVAL,
        latest_version="1.3.0",
    )
    monkeypatch.setattr(update_check.time, "time", lambda: now)

    with mock.patch.object(
        update_check, "_fetch_latest_version", return_value="1.4.0"
    ) as fetch:
        assert update_check.check("1.3.0") == "1.4.0"
    fetch.assert_called_once_with()


def test_future_cache_timestamp_is_not_trusted(fake_cache, monkeypatch):
    now = 50_000.0
    _write_cache(
        fake_cache,
        checked_at=now + 10,
        latest_version="9.0.0",
    )
    monkeypatch.setattr(update_check.time, "time", lambda: now)

    with mock.patch.object(
        update_check, "_fetch_latest_version", return_value="1.4.0"
    ):
        assert update_check.check("1.3.0") == "1.4.0"


def test_corrupt_cache_is_replaced(fake_cache):
    fake_cache.parent.mkdir(parents=True)
    fake_cache.write_text("not json {{{", encoding="utf-8")

    with mock.patch.object(
        update_check, "_fetch_latest_version", return_value="1.4"
    ):
        assert update_check.check("1.3") == "1.4"

    saved = json.loads(fake_cache.read_text(encoding="utf-8"))
    assert saved["latest_version"] == "1.4"
    assert isinstance(saved["checked_at"], float)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"checked_at": True, "latest_version": "1.4"},
        {"checked_at": float("inf"), "latest_version": "1.4"},
        {"checked_at": 10, "latest_version": [1, 4]},
        {"checked_at": 10, "latest_version": "not a version"},
    ],
)
def test_invalid_cache_schema_self_heals(fake_cache, payload):
    fake_cache.parent.mkdir(parents=True)
    fake_cache.write_text(json.dumps(payload), encoding="utf-8")

    with mock.patch.object(
        update_check, "_fetch_latest_version", return_value="1.4.0"
    ):
        assert update_check.check("1.3.0") == "1.4.0"

    saved = json.loads(fake_cache.read_text(encoding="utf-8"))
    assert saved["latest_version"] == "1.4.0"


def test_failed_request_is_also_cached_for_a_day(fake_cache):
    with mock.patch.object(
        update_check, "_fetch_latest_version", return_value=None
    ) as fetch:
        assert update_check.check("1.3.0") is None
        assert update_check.check("1.3.0") is None

    fetch.assert_called_once_with()
    saved = json.loads(fake_cache.read_text(encoding="utf-8"))
    assert saved["latest_version"] is None


def test_unexpected_fetch_failure_is_negative_cached(fake_cache):
    with mock.patch.object(
        update_check, "_fetch_latest_version", side_effect=RuntimeError("broken HTTP")
    ) as fetch:
        assert update_check.check("1.3.0") is None
        assert update_check.check("1.3.0") is None

    fetch.assert_called_once_with()


def test_failed_refresh_keeps_last_known_version(fake_cache, monkeypatch):
    now = 1_000_000.0
    _write_cache(
        fake_cache,
        checked_at=now - update_check.CHECK_INTERVAL - 1,
        latest_version="1.4.0",
    )
    monkeypatch.setattr(update_check.time, "time", lambda: now)

    with mock.patch.object(update_check, "_fetch_latest_version", return_value=None):
        assert update_check.check("1.3.0") == "1.4.0"

    saved = json.loads(fake_cache.read_text(encoding="utf-8"))
    assert saved == {"checked_at": now, "latest_version": "1.4.0"}


def test_fetch_reads_pypi_json_and_normalizes_version(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def read(self):
            return b'{"info": {"version": "v1.4.0"}}'

    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return Response()

    monkeypatch.setattr(update_check.urllib.request, "urlopen", fake_urlopen)

    assert update_check._fetch_latest_version() == "1.4.0"
    request, timeout = calls[0]
    assert request.full_url == update_check.PYPI_URL
    assert request.get_header("User-agent") == "flashbar-update-check"
    assert timeout == update_check.REQUEST_TIMEOUT


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b"{}",
        b'{"info": {}}',
        b'{"info": {"version": "bad version"}}',
        b"\xff\xfe",
    ],
)
def test_fetch_rejects_bad_responses(monkeypatch, body):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def read(self):
            return body

    monkeypatch.setattr(
        update_check.urllib.request, "urlopen", lambda *args, **kwargs: Response()
    )
    assert update_check._fetch_latest_version() is None


@pytest.mark.parametrize(
    "error",
    [urllib.error.URLError("offline"), TimeoutError("slow network")],
)
def test_fetch_swallows_network_errors(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(update_check.urllib.request, "urlopen", fail)
    assert update_check._fetch_latest_version() is None


def test_notice_has_requested_two_line_format(fake_cache, monkeypatch):
    monkeypatch.setattr(update_check, "_notice_allowed", lambda stream: True)
    stream = TTYStream()
    with mock.patch.object(update_check, "_fetch_latest_version", return_value="1.4"):
        update_check.maybe_notify("1.3", stream=stream)

    assert stream.getvalue() == (
        "ℹ  flashbar 1.4 is available (you have 1.3).\n"
        "Run: pip install -U flashbar\n"
    )


def test_notice_is_not_repeated_during_same_day(fake_cache, monkeypatch):
    monkeypatch.setattr(update_check, "_notice_allowed", lambda stream: True)
    first = TTYStream()
    second = TTYStream()
    with mock.patch.object(
        update_check, "_fetch_latest_version", return_value="1.4.0"
    ) as fetch:
        update_check.maybe_notify("1.3.0", stream=first)
        update_check.maybe_notify("1.3.0", stream=second)

    assert "flashbar 1.4.0" in first.getvalue()
    assert second.getvalue() == ""
    fetch.assert_called_once_with()


def test_narrow_terminal_gets_ascii_marker(fake_cache, monkeypatch):
    monkeypatch.setattr(update_check, "_notice_allowed", lambda stream: True)
    buffer = io.BytesIO()
    stream = EncodedTTY(buffer, encoding="cp1251")
    with mock.patch.object(update_check, "_fetch_latest_version", return_value="1.4"):
        update_check.maybe_notify("1.3", stream=stream)
    stream.flush()

    output = buffer.getvalue().decode("cp1251")
    assert output.startswith("[i]  flashbar 1.4 is available")


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("FLASHBAR_NO_UPDATE_CHECK", "1"),
        ("FLASHBAR_NO_UPDATE_CHECK", "yes"),
        ("CI", "true"),
        ("GITHUB_ACTIONS", "1"),
    ],
)
def test_environment_suppresses_notice(
    fake_cache, monkeypatch, variable, value
):
    monkeypatch.setattr(sys, "stdout", TTYStream())
    monkeypatch.setenv(variable, value)
    stream = TTYStream()
    with mock.patch.object(update_check, "check") as check:
        update_check.maybe_notify("1.3.0", stream=stream)
    check.assert_not_called()
    assert stream.getvalue() == ""


def test_false_environment_values_do_not_disable_check(monkeypatch):
    for value in ("", "0", "false", "no", "off"):
        monkeypatch.setenv("FLASHBAR_NO_UPDATE_CHECK", value)
        assert update_check._is_disabled() is False


def test_no_update_check_argument_disables_network(fake_cache, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["app", "--no-update-check"])
    with mock.patch.object(update_check, "_fetch_latest_version") as fetch:
        assert update_check.check("1.3.0") is None
    fetch.assert_not_called()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--json"],
        ["--jsonl"],
        ["--ndjson"],
        ["--json-output"],
        ["--format=json"],
        ["--output=json"],
        ["--output-format=json"],
        ["--format", "json"],
        ["--output", "jsonl"],
        ["--output-format", "ndjson"],
    ],
)
def test_machine_output_arguments_suppress_notice(
    fake_cache, monkeypatch, arguments
):
    monkeypatch.setattr(sys, "stdout", TTYStream())
    monkeypatch.setattr(sys, "argv", ["app", *arguments])
    stream = TTYStream()
    with mock.patch.object(update_check, "check") as check:
        update_check.maybe_notify("1.3.0", stream=stream)
    check.assert_not_called()


def test_redirected_stdout_suppresses_notice(fake_cache, monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    with mock.patch.object(update_check, "check") as check:
        update_check.maybe_notify("1.3.0", stream=TTYStream())
    check.assert_not_called()


def test_notice_never_raises(fake_cache, monkeypatch):
    monkeypatch.setattr(update_check, "_notice_allowed", lambda stream: True)
    with mock.patch.object(update_check, "check", side_effect=RuntimeError("boom")):
        update_check.maybe_notify("1.3.0", stream=TTYStream())


def test_broken_tty_probe_never_raises():
    class BrokenTTY(TTYStream):
        def isatty(self):
            raise RuntimeError("terminal disappeared")

    update_check.maybe_notify("1.3.0", stream=BrokenTTY())


def test_interactive_terminal_allows_notice(monkeypatch):
    monkeypatch.setattr(sys, "stdout", TTYStream())
    assert update_check._notice_allowed(TTYStream()) is True


def test_automatic_check_runs_only_once_per_process(monkeypatch):
    monkeypatch.setattr(update_check, "_notice_allowed", lambda stream: True)
    output = TTYStream()
    with mock.patch.object(update_check, "maybe_notify") as notify:
        update_check._maybe_notify_once(output)
        update_check._maybe_notify_once(output)
    notify.assert_called_once_with(stream=output)


def test_bar_checks_after_successful_default_output(monkeypatch):
    monkeypatch.setattr(bar_module.sys, "stderr", TTYStream())
    with mock.patch.object(bar_module, "_maybe_notify_once") as notify:
        bar = Bar(1)
        bar.update()
    notify.assert_called_once_with(bar.file)


def test_bar_set_checks_after_completion(monkeypatch):
    monkeypatch.setattr(bar_module.sys, "stderr", TTYStream())
    with mock.patch.object(bar_module, "_maybe_notify_once") as notify:
        bar = Bar(2)
        bar.set(2)
    notify.assert_called_once_with(bar.file)


def test_bar_set_total_checks_after_completion(monkeypatch):
    monkeypatch.setattr(bar_module.sys, "stderr", TTYStream())
    with mock.patch.object(bar_module, "_maybe_notify_once") as notify:
        bar = Bar(None)
        bar.update(2)
        bar.set_total(2)
    notify.assert_called_once_with(bar.file)


def test_bar_custom_stream_never_triggers_global_notice():
    with mock.patch.object(bar_module, "_maybe_notify_once") as notify:
        Bar(1, file=TTYStream()).update()
    notify.assert_not_called()


def test_bar_uses_stderr_captured_at_construction(monkeypatch):
    redirected = io.StringIO()
    monkeypatch.setattr(sys, "stderr", redirected)
    bar = Bar(1)
    monkeypatch.setattr(sys, "stderr", TTYStream())
    monkeypatch.setattr(sys, "stdout", TTYStream())

    with mock.patch.object(update_check, "maybe_notify") as notify:
        bar.update()
    notify.assert_not_called()


def test_bar_exception_does_not_trigger_notice(monkeypatch):
    monkeypatch.setattr(bar_module.sys, "stderr", TTYStream())
    with mock.patch.object(bar_module, "_maybe_notify_once") as notify:
        with pytest.raises(RuntimeError, match="task failed"):
            with Bar(2):
                raise RuntimeError("task failed")
    notify.assert_not_called()


def test_bar_exception_after_completion_does_not_trigger_notice(monkeypatch):
    monkeypatch.setattr(bar_module.sys, "stderr", TTYStream())
    with mock.patch.object(bar_module, "_maybe_notify_once") as notify:
        with pytest.raises(RuntimeError, match="later failure"):
            with Bar(1) as bar:
                bar.update()
                raise RuntimeError("later failure")
    notify.assert_not_called()


def test_completed_bar_context_checks_on_clean_exit(monkeypatch):
    monkeypatch.setattr(bar_module.sys, "stderr", TTYStream())
    with mock.patch.object(bar_module, "_maybe_notify_once") as notify:
        with Bar(1) as bar:
            bar.update()
    notify.assert_called_once_with(bar.file)


def test_spinner_checks_after_successful_stop(monkeypatch):
    monkeypatch.setattr(spinner_module.sys, "stderr", io.StringIO())
    with mock.patch.object(spinner_module, "_maybe_notify_once") as notify:
        spinner = Spinner()
        spinner.start()
        spinner.stop("done")
    notify.assert_called_once_with(spinner.file)


def test_spinner_exception_does_not_trigger_notice(monkeypatch):
    monkeypatch.setattr(spinner_module.sys, "stderr", io.StringIO())
    with mock.patch.object(spinner_module, "_maybe_notify_once") as notify:
        with pytest.raises(RuntimeError, match="task failed"):
            with Spinner("work"):
                raise RuntimeError("task failed")
    notify.assert_not_called()


def test_spinner_stopped_inside_failing_context_does_not_notify(monkeypatch):
    monkeypatch.setattr(spinner_module.sys, "stderr", io.StringIO())
    with mock.patch.object(spinner_module, "_maybe_notify_once") as notify:
        with pytest.raises(RuntimeError, match="later failure"):
            with Spinner("work") as spinner:
                spinner.stop("done")
                raise RuntimeError("later failure")
    notify.assert_not_called()


def test_spinner_stopped_inside_clean_context_notifies(monkeypatch):
    monkeypatch.setattr(spinner_module.sys, "stderr", io.StringIO())
    with mock.patch.object(spinner_module, "_maybe_notify_once") as notify:
        with Spinner("work") as spinner:
            spinner.stop("done")
    notify.assert_called_once_with(spinner.file)


def test_spinner_context_keeps_compatible_stop_override(monkeypatch):
    monkeypatch.setattr(spinner_module.sys, "stderr", io.StringIO())

    class CustomSpinner(Spinner):
        def stop(self, final_text=None):
            super().stop(final_text)

    with mock.patch.object(spinner_module, "_maybe_notify_once"):
        with CustomSpinner("work"):
            pass


def test_cache_write_uses_atomic_replace(fake_cache, monkeypatch):
    real_replace = update_check.os.replace
    replacements = []

    def recording_replace(source, destination):
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(update_check.os, "replace", recording_replace)
    update_check._save_cache({"checked_at": 100.0, "latest_version": "1.4.0"})

    assert len(replacements) == 1
    assert replacements[0][1] == fake_cache
    assert list(fake_cache.parent.glob(".*.tmp")) == []


def test_failed_cache_serialization_removes_temporary_file(fake_cache):
    update_check._save_cache({"checked_at": object()})
    assert not fake_cache.exists()
    assert list(fake_cache.parent.glob(".*.tmp")) == []


def test_cache_read_error_falls_back_to_network(fake_cache, monkeypatch):
    with mock.patch.object(Path, "read_text", side_effect=OSError("no access")):
        with mock.patch.object(
            update_check, "_fetch_latest_version", return_value="1.4.0"
        ):
            assert update_check.check("1.3.0") == "1.4.0"


def test_xdg_cache_location(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert update_check._cache_path() == (
        tmp_path / "flashbar" / "update-check.json"
    )


def test_normalize_version_matches_packaging():
    assert update_check._normalize_version("v1.4.0") == str(Version("1.4.0"))
