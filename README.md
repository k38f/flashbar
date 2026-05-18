# ⚡ flashbar

🌐 **English** · [简体中文](README.zh-CN.md)

<sub>*Parts of this README were translated and edited with AI.*</sub>

A progress bar — and now pretty CLI output — you can read end-to-end in one coffee break.

One package. Tiny. No magic. No dependencies. Python 3.8+.

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

That's it. One import, one line.

## What's new in 1.2

- **Pretty output module** — `panel()`, `rule()`, plus `success()`, `error()`, `warn()`, `info()` indicators. Wrap any text in styled boxes without pulling in rich.
- All 1.1 improvements: smooth bar rendering, TTY detection, throttled redraws, type hints, better short-task ETA.

## Pretty output

Build styled CLI output with a few small functions:

```python
from flashbar import panel, rule, success, error, warn, info

print(panel("Build complete\n42 files compiled in 1.2s",
            title="Status", color="green"))

print(rule("Status indicators"))

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

Methods: `.update(step=1)`, `.set(value)`, context manager.

#### `track(iterable, **options)`

Same options as `Bar`, plus `total=` for iterables without `len()`.

#### `Spinner(label, **options)`

| Param   | Type  | Default  | Description              |
|---------|-------|----------|--------------------------|
| `label` | str   | `""`     | Text next to spinner     |
| `style` | str   | `"dots"` | Spinner animation style  |
| `color` | str   | `"cyan"` | Color (name or hex)      |
| `speed` | float | `0.08`   | Seconds between frames   |

Methods: `.start()`, `.stop(final_text=None)`, context manager.

### Pretty output

#### `panel(text, **options) -> str`

| Param     | Type | Default     | Description                                |
|-----------|------|-------------|--------------------------------------------|
| `text`    | str  | required    | Body content (may contain newlines)        |
| `title`   | str  | `None`      | Optional title in the top border           |
| `color`   | str  | `None`      | Border color (name or hex)                 |
| `width`   | int  | `None`      | Total width. None = auto-fit content       |
| `style`   | str  | `"rounded"` | rounded, square, double, heavy, ascii      |
| `padding` | int  | `1`         | Horizontal padding inside the box          |

#### `rule(label="", width=None, color=None) -> str`

Horizontal divider. Empty `label` for plain line.

#### Status indicators (return `str`)

```python
success("ok")  # ✓ ok
error("no")    # ✗ no
warn("hmm")    # ⚠ hmm
info("fyi")    # ℹ fyi
```

#### `print_panel(text, title=None, color=None, file=None, **kwargs)`

Convenience: builds and prints a panel. Strips styling automatically when output isn't a TTY.

## License

MIT
