# ⚡ flashbar

🌐 **English** · [简体中文](docs/README.zh-CN.md) · [Русский](docs/README.ru.md)

![README: generated with AI](https://img.shields.io/badge/README-generated%20with%20AI-6f42c1)

Lightweight progress bars and formatted CLI output for Python 3.8+.
No runtime dependencies.

<p align="center">
  <img src="demo.gif" alt="flashbar demo" width="600">
</p>

## Install

```bash
pip install flashbar
```

## Quick start

```python
from flashbar import track
import time

for item in track(range(100), label="Downloading"):
    time.sleep(0.02)
```

## Formatted output

Build styled CLI output with a few small functions:

```python
from flashbar import panel, rule, success, error, warn, info

print(panel("Build complete\n42 files compiled in 1.2s",
            title="Status", color="green", width=47))

print(rule("Status indicators", width=51))

print(success("Tests passed"))
print(error("Build failed"))
print(warn("Deprecated API"))
print(info("Update available"))
```

Output:

```
╭─ Status ────────────────────────────────────╮
│ Build complete                              │
│ 42 files compiled in 1.2s                   │
╰─────────────────────────────────────────────╯

──────────────── Status indicators ────────────────

✓ Tests passed
✗ Build failed
⚠ Deprecated API
ℹ Update available
```

### Panel styles

Five border styles available:

```python
panel("body", style="rounded")  # ╭ ╮ ╰ ╯  (default)
panel("body", style="square")   # ┌ ┐ └ ┘
panel("body", style="double")   # ╔ ╗ ╚ ╝
panel("body", style="heavy")    # ┏ ┓ ┗ ┛
panel("body", style="ascii")    # + + + +
```

Auto-fits to content, or pass `width=N` for a fixed size. Custom `color` (named or hex) and `padding` are supported.

Pass `plain=True` to `panel()`, `rule()`, or a status helper for ANSI-free ASCII decoration. Nested ANSI sequences in user text are stripped in this mode:

```python
print(success("Tests passed", plain=True))  # [OK] Tests passed
print(rule("Build log", width=32, plain=True))
```

With the default `plain=None`, these helpers use styled Unicode only when stdout is an encodable TTY. Pass `plain=False` to force styling.

### Rule

Horizontal divider, optionally with a centered label:

```python
print(rule())                         # full-width line
print(rule("Section 1"))              # centered label
print(rule("Done", color="green"))    # colored
```

### Print helper

If you don't want to call `print()` yourself:

```python
from flashbar import print_panel

print_panel("Connection failed", title="Error", color="red")
```

When output isn't a TTY (logs, CI), styling strips automatically — your log files stay clean.

## Progress bar

```python
from flashbar import Bar

bar = Bar(100, label="Processing", theme="green")
for i in range(100):
    bar.update()

# or jump to a specific value
bar = Bar(100)
bar.set(50)  # jump to 50%
bar.set(100) # done
```

### With context manager

Automatically completes the bar on exit, even on exceptions:

```python
with Bar(100, theme="retro", label="Building") as bar:
    for i in range(100):
        do_work()
        bar.update()
```

### ETA and speed

```python
# ETA is on by default
bar = Bar(1000, label="Training", show_eta=True)

# show items/sec too
bar = Bar(1000, label="Training", show_speed=True)
```

### Smooth rendering

Sub-character rendering makes bars look much more fluid. It's auto-enabled when the fill character is `█`, and you can toggle it explicitly:

```python
# always smooth
Bar(100, smooth=True)

# always classic
Bar(100, smooth=False)
```

## Spinner

For tasks where you don't know the total:

```python
from flashbar import Spinner

with Spinner("Loading data...", style="dots"):
    load_big_file()

# manual control
sp = Spinner("Thinking...", style="circle", color="magenta")
sp.start()
result = heavy_computation()
sp.stop("Done!")
```

## Themes

See the demo GIF above to see each theme in action with real colors.

```python
from flashbar import Bar

for name in ["default", "green", "red", "retro", "minimal", "slim", "dots", "arrow"]:
    bar = Bar(30, theme=name, label=f"{name:8s}")
    for _ in range(30):
        bar.update()
```

| Theme     | Look                       |
|-----------|----------------------------|
| `default` | `█████░░░░░` 🔵 blue       |
| `green`   | `█████░░░░░` 🟢 green      |
| `red`     | `█████░░░░░` 🔴 red        |
| `retro`   | `#####.....` 🟡 yellow     |
| `minimal` | `─────     ` ⚪ white      |
| `slim`    | `━━━━━╺╺╺╺╺` 🔵 cyan      |
| `dots`    | `●●●●●○○○○○` 🟣 magenta   |
| `arrow`   | `▸▸▸▸▸▹▹▹▹▹` 🔵 blue      |

## Spinner styles

| Style    | Frames            |
|----------|-------------------|
| `dots`   | ⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ |
| `line`   | - \ \| /          |
| `circle` | ◐ ◓ ◑ ◒          |
| `bounce` | ⠁ ⠂ ⠄ ⠂          |
| `arrows` | ← ↑ → ↓          |
| `grow`   | ▏ ▎ ▍ ▌ ▋ ▊ ▉ █  |
| `moon`   | 🌑🌒🌓🌔🌕🌖🌗🌘   |

## Custom colors

```python
# named
Bar(100, color="cyan", label="Cyan bar")

# any hex color
Bar(100, color="#FF5733", label="Orange bar")
Bar(100, color="#00FF99", label="Mint bar")
```

## Custom characters

```python
Bar(100, fill="▓", empty="▒")
Bar(100, fill="=", empty="-")
Bar(100, fill="●", empty="○", color="#FF69B4")
```

Custom `fill` and `empty` values must each occupy exactly one terminal cell.

## Generators and iterators

`track()` works with anything that has `len()`. For generators, pass `total=`:

```python
def my_generator():
    for i in range(1000):
        yield i

for item in track(my_generator(), total=1000, label="Generating"):
    process(item)
```

## Behavior in non-TTY environments

When output is piped to a file or running in CI, flashbar detects that automatically and stays quiet — only the final line is printed, without any escape codes:

```bash
python myscript.py 2> log.txt    # log.txt stays clean
python myscript.py 2>&1 | tee    # no garbled output
```

## API reference

### Progress

#### `Bar(total, **options)`

| Param        | Type   | Default     | Description                         |
|--------------|--------|-------------|-------------------------------------|
| `total`      | int    | required    | Number of steps                     |
| `width`      | int    | `40`        | Bar width in characters             |
| `theme`      | str    | `"default"` | Theme name                          |
| `label`      | str    | `""`        | Text before the bar                 |
| `color`      | str    | `None`      | Override color (name or hex)        |
| `fill`       | str    | `None`      | Override fill character             |
| `empty`      | str    | `None`      | Override empty character            |
| `show_eta`   | bool   | `True`      | Show estimated time remaining       |
| `show_speed` | bool   | `False`     | Show items/sec                      |
| `smooth`     | bool   | `None`      | Sub-character rendering. None = auto |

Methods: `.update(step=1)`, `.set(value)`, context manager. Negative steps are rejected. Calling `.set()` below the total reopens a completed bar and restarts its timer.

#### `track(iterable, **options)`

Same options as `Bar`, plus `total=` for iterables without `len()`.

#### `Spinner(label, **options)`

| Param   | Type  | Default  | Description              |
|---------|-------|----------|--------------------------|
| `label` | str   | `""`     | Text next to spinner     |
| `style` | str   | `"dots"` | Spinner animation style  |
| `color` | str   | `"cyan"` | Color (name or hex)      |
| `speed` | float | `0.08`   | Positive finite seconds between frames |

Methods: `.start()`, `.stop(final_text=None)`, context manager.

### Formatted output

#### `panel(text, **options) -> str`

| Param     | Type | Default     | Description                                |
|-----------|------|-------------|--------------------------------------------|
| `text`    | str  | required    | Body content (may contain newlines)        |
| `title`   | str  | `None`      | Optional title in the top border           |
| `color`   | str  | `None`      | Border color (name or hex)                 |
| `width`   | int  | `None`      | Total width. None = auto-fit content       |
| `style`   | str  | `"rounded"` | rounded, square, double, heavy, ascii      |
| `padding` | int  | `1`         | Horizontal padding inside the box          |
| `plain`   | bool or None | `None` | Auto-detect output; True = ASCII, False = styled |

#### `rule(label="", width=None, color=None, plain=None) -> str`

Horizontal divider. Empty `label` creates an unlabelled line. Its visible width always matches `width`. With `plain=None`, output is styled only when `sys.stdout` is a TTY; pass `plain=False` to force styling.

#### Status indicators (return `str`)

Status helpers use the same `plain=None` auto-detection. Pass `plain=False` to force color or `plain=True` for portable ASCII text.

```python
success("ok")  # ✓ ok
error("no")    # ✗ no
warn("hmm")    # ⚠ hmm
info("fyi")    # ℹ fyi

success("ok", plain=True)  # [OK] ok
```

#### `print_panel(text, title=None, color=None, file=None, **kwargs)`

Builds and prints a panel. Non-TTY output is compact by default. Pass `plain=True` to keep a full ASCII panel or `plain=False` to force the styled panel.

## License

MIT
