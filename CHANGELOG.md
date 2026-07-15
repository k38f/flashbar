# Changelog

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
