# Changelog

## 1.4.0

### Added

- Weekly cached PyPI update notices after successful progress bars and spinners.
- Opt-outs for `--no-update-check`, `FLASHBAR_NO_UPDATE_CHECK`, CI, GitHub Actions,
  redirected streams, and common JSON output modes.
- A public `maybe_notify()` helper for CLI applications that only use formatted
  output helpers.
- Unit-aware counts and speeds with IEC byte scaling and SI scaling for other
  units.
- Dynamic labels and postfix fields through `set_label()` and `set_postfix()`.
- Indeterminate `Bar(None)` progress that can switch to a known total with
  `set_total()`.
- Transient progress bars that clean up their terminal output after completion.

### Changed

- Use `packaging` for PEP 440-compliant release comparisons.

## 1.3.0

### Fixed

- Start progress timing before the first item and keep completed/reopened bars consistent.
- Reject invalid progress steps, widths, glyphs, spinner speeds, and empty frame sets.
- Make large integer totals, interrupted `track()` calls, spinner restarts, and output failures safe.
- Preserve user and iterable exceptions when terminal cleanup also fails.
- Close open ANSI styles and OSC 8 hyperlinks before rendering adjacent output.
- Count terminal cells correctly for wide, combining, and emoji text.
- Keep panels and rules within their requested width without cutting ANSI sequences.
- Strip nested ANSI styling from non-TTY panel output and normalise CRLF input.
- Validate panel geometry and preserve explicitly supplied output streams.
- Fall back to ASCII decoration when a print target cannot encode box characters.

### Added

- `plain=True` output for panels, rules, and status helpers.
- Automatic plain output from panels, rules, and status helpers for redirected or legacy stdout.
- Python 3.8-compatible PEP 639 builds, Windows CI, typing, and distribution checks.

## 1.2.0

### Added

- Formatted CLI output with `panel()`, `print_panel()`, and `rule()`.
- Status helpers: `success()`, `error()`, `warn()`, and `info()`.
- Type information for static type checkers.

### Improved

- Smoother progress-bar rendering.
- TTY detection and cleaner output in logs and CI.
- Throttled redraws to reduce terminal overhead.
- More stable ETA estimates for short tasks.
