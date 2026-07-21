from __future__ import annotations

import json
import math
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, IO, Optional

from packaging.version import InvalidVersion, Version


PACKAGE_NAME = "flashbar"
PYPI_URL = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
CHECK_INTERVAL = 7 * 24 * 60 * 60
REQUEST_TIMEOUT = 2.0

_FALSE_VALUES = {"", "0", "false", "no", "off"}
_state_lock = threading.RLock()
_automatic_attempted = False


def _cache_path() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        base = Path(xdg)
    elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"])
    else:
        base = Path.home() / ".cache"
    return base / PACKAGE_NAME / "update-check.json"


def _env_is_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() not in _FALSE_VALUES


def _has_arg(name: str) -> bool:
    return any(arg == name for arg in sys.argv[1:] if isinstance(arg, str))


def _machine_output_requested() -> bool:
    args = [arg.strip().lower() for arg in sys.argv[1:] if isinstance(arg, str)]
    for index, value in enumerate(args):
        if value in {"--json", "--jsonl", "--ndjson", "--json-output"}:
            return True
        if value.startswith(
            ("--format=json", "--output=json", "--output-format=json")
        ):
            return True
        if value in {"--format", "--output", "--output-format"}:
            if index + 1 < len(args) and args[index + 1] in {
                "json", "jsonl", "ndjson",
            }:
                return True
    return False


def _is_disabled() -> bool:
    return _env_is_true("FLASHBAR_NO_UPDATE_CHECK") or _has_arg(
        "--no-update-check"
    )


def _stream_is_tty(stream: IO[str]) -> bool:
    try:
        return bool(getattr(stream, "isatty", lambda: False)())
    except Exception:
        return False


def _notice_allowed(stream: IO[str]) -> bool:
    if _is_disabled() or _env_is_true("CI") or _env_is_true("GITHUB_ACTIONS"):
        return False
    if _machine_output_requested():
        return False
    # stdout may contain JSON even though progress itself is written to stderr.
    return _stream_is_tty(stream) and _stream_is_tty(sys.stdout)


def _normalize_version(value: object) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return str(Version(value.strip()))
    except InvalidVersion:
        return None


def _valid_timestamp(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except (OverflowError, ValueError):
        return None
    if not math.isfinite(result) or result < 0:
        return None
    return result


def _load_cache() -> Optional[Dict[str, object]]:
    try:
        payload = json.loads(_cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(payload, dict):
        return None

    checked_at = _valid_timestamp(payload.get("checked_at"))
    if checked_at is None:
        return None

    raw_latest = payload.get("latest_version")
    latest = None if raw_latest is None else _normalize_version(raw_latest)
    if raw_latest is not None and latest is None:
        return None

    cache: Dict[str, object] = {
        "checked_at": checked_at,
        "latest_version": latest,
    }
    notified_at = _valid_timestamp(payload.get("notified_at"))
    notified_version = _normalize_version(payload.get("notified_version"))
    if notified_at is not None and notified_version is not None:
        cache["notified_at"] = notified_at
        cache["notified_version"] = notified_version
    return cache


def _save_cache(data: Dict[str, object]) -> None:
    path = _cache_path()
    temp_path: Optional[Path] = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(10):
            candidate = path.parent / (
                f".{path.name}-{secrets.token_hex(8)}.tmp"
            )
            try:
                stream = candidate.open("x", encoding="utf-8", newline="\n")
            except FileExistsError:
                continue
            temp_path = candidate
            with stream:
                json.dump(data, stream, separators=(",", ":"))
            break
        if temp_path is None:
            return
        os.replace(temp_path, path)
        temp_path = None
    except (OSError, TypeError, ValueError):
        pass
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


def _fetch_latest_version() -> Optional[str]:
    try:
        request = urllib.request.Request(
            PYPI_URL,
            headers={"User-Agent": f"{PACKAGE_NAME}-update-check"},
        )
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        info = payload.get("info")
        if not isinstance(info, dict):
            return None
        return _normalize_version(info.get("version"))
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        AttributeError,
        UnicodeError,
    ):
        return None


def _is_newer(latest: object, current: object) -> bool:
    latest_version = _normalize_version(latest)
    current_version = _normalize_version(current)
    if latest_version is None or current_version is None:
        return False
    return Version(latest_version) > Version(current_version)


def _is_fresh(timestamp: object, now: float) -> bool:
    checked_at = _valid_timestamp(timestamp)
    if checked_at is None:
        return False
    age = now - checked_at
    return 0 <= age < CHECK_INTERVAL


def check(current_version: str, force: bool = False) -> Optional[str]:
    """Return the latest version when PyPI has a newer flashbar release."""
    if _is_disabled():
        return None

    try:
        with _state_lock:
            now = time.time()
            cache = _load_cache()
            if cache is not None and not force and _is_fresh(
                cache.get("checked_at"), now
            ):
                latest = cache.get("latest_version")
                return str(latest) if _is_newer(latest, current_version) else None

            previous_latest = cache.get("latest_version") if cache else None
            try:
                fetched = _fetch_latest_version()
            except Exception:
                fetched = None
            latest = _normalize_version(fetched) or _normalize_version(previous_latest)

            data = dict(cache) if cache is not None else {}
            data.update({"checked_at": now, "latest_version": latest})
            _save_cache(data)
            return latest if _is_newer(latest, current_version) else None
    except Exception:
        return None


def _write_notice(stream: IO[str], latest: str, current: str) -> None:
    message = (
        f"ℹ  {PACKAGE_NAME} {latest} is available (you have {current}).\n"
        f"Run: pip install -U {PACKAGE_NAME}\n"
    )
    encoding = getattr(stream, "encoding", None)
    if isinstance(encoding, str):
        try:
            message.encode(encoding)
        except (LookupError, UnicodeEncodeError):
            message = message.replace("ℹ", "[i]")
    try:
        stream.write(message)
    except UnicodeEncodeError:
        stream.write(message.replace("ℹ", "[i]"))
    stream.flush()


def maybe_notify(
    current_version: Optional[str] = None,
    stream: Optional[IO[str]] = None,
    *,
    force: bool = False,
) -> None:
    """Print a quiet update notice when a newer release is available."""
    output = sys.stderr if stream is None else stream
    try:
        if not _notice_allowed(output):
            return
        if current_version is None:
            from . import __version__

            current_version = __version__

        latest = check(current_version, force=force)
        current = _normalize_version(current_version)
        if latest is None or current is None:
            return

        with _state_lock:
            now = time.time()
            cache = _load_cache()
            if (
                not force
                and cache is not None
                and cache.get("notified_version") == latest
                and _is_fresh(cache.get("notified_at"), now)
            ):
                return

            _write_notice(output, latest, current)
            data = dict(cache) if cache is not None else {
                "checked_at": now,
                "latest_version": latest,
            }
            data.update({"notified_at": now, "notified_version": latest})
            _save_cache(data)
    except Exception:
        pass


def _maybe_notify_once(stream: Optional[IO[str]] = None) -> None:
    global _automatic_attempted

    output = sys.stderr if stream is None else stream
    try:
        if not _notice_allowed(output):
            return
        with _state_lock:
            if _automatic_attempted:
                return
            _automatic_attempted = True
        maybe_notify(stream=output)
    except Exception:
        pass
