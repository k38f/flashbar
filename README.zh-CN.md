# ⚡ flashbar

🌐 [English](README.md) · **简体中文**

<sub>*本文档部分内容由 AI 翻译和润色。*</sub>

进度条 —— 现在还有美观的 CLI 输出 —— 你能在一杯咖啡的时间里读完整个库。

单包。轻量。无魔法。零依赖。Python 3.8+。

<p align="center">
  <img src="demo.gif" alt="flashbar 演示" width="600">
</p>

## 安装

```bash
pip install flashbar
```

## 快速开始

```python
from flashbar import track
import time

for item in track(range(100), label="Downloading"):
    time.sleep(0.02)
```

就这么简单。一行 import,一行调用。

## 1.2 版本新特性

- **美观输出模块** —— `panel()`、`rule()`,以及 `success()`、`error()`、`warn()`、`info()` 状态指示器。无需 rich,即可将任意文本包装在样式化的盒子中。
- 1.1 的所有改进:平滑进度条渲染、TTY 检测、限频重绘、类型注解、短任务的更好 ETA。

## 美观输出

通过几个小函数构建样式化的 CLI 输出:

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

输出:

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

### Panel 样式

可选五种边框样式:

```python
panel("body", style="rounded")  # ╭ ╮ ╰ ╯  (默认)
panel("body", style="square")   # ┌ ┐ └ ┘
panel("body", style="double")   # ╔ ╗ ╚ ╝
panel("body", style="heavy")    # ┏ ┓ ┗ ┛
panel("body", style="ascii")    # + + + +
```

自动适应内容宽度,或传入 `width=N` 固定大小。支持自定义 `color`(颜色名或 hex)和 `padding`。

### Rule 分隔线

水平分隔线,可以加居中标签:

```python
print(rule())                         # 整行分隔
print(rule("Section 1"))              # 居中标签
print(rule("Done", color="green"))    # 带颜色
```

### print 辅助函数

不想自己调 `print()`:

```python
from flashbar import print_panel

print_panel("Connection failed", title="Error", color="red")
```

当输出不是 TTY(日志、CI)时,自动剥离样式 —— 日志文件保持干净。

## 进度条

```python
from flashbar import Bar

bar = Bar(100, label="Processing", theme="green")
for i in range(100):
    bar.update()

# 也可以直接跳到某个值
bar = Bar(100)
bar.set(50)  # 跳到 50%
bar.set(100) # 完成
```

### 配合 context manager

退出时自动完成进度条,即使发生异常也是如此:

```python
with Bar(100, theme="retro", label="Building") as bar:
    for i in range(100):
        do_work()
        bar.update()
```

### ETA 与速度

```python
# ETA 默认开启
bar = Bar(1000, label="Training", show_eta=True)

# 同时显示每秒处理数
bar = Bar(1000, label="Training", show_speed=True)
```

### 平滑渲染

亚字符渲染让进度条看起来更流畅。当填充字符为 `█` 时自动启用,你也可以显式控制:

```python
# 始终平滑
Bar(100, smooth=True)

# 始终经典
Bar(100, smooth=False)
```

## Spinner

适用于不知道总数的任务:

```python
from flashbar import Spinner

with Spinner("Loading data...", style="dots"):
    load_big_file()

# 手动控制
sp = Spinner("Thinking...", style="circle", color="magenta")
sp.start()
result = heavy_computation()
sp.stop("Done!")
```

## 主题

请查看上方演示 GIF,了解各主题在真实色彩下的效果。

```python
from flashbar import Bar

for name in ["default", "green", "red", "retro", "minimal", "slim", "dots", "arrow"]:
    bar = Bar(30, theme=name, label=f"{name:8s}")
    for _ in range(30):
        bar.update()
```

| 主题      | 外观                       |
|-----------|----------------------------|
| `default` | `█████░░░░░` 🔵 蓝色       |
| `green`   | `█████░░░░░` 🟢 绿色       |
| `red`     | `█████░░░░░` 🔴 红色       |
| `retro`   | `#####.....` 🟡 黄色       |
| `minimal` | `─────     ` ⚪ 白色       |
| `slim`    | `━━━━━╺╺╺╺╺` 🔵 青色       |
| `dots`    | `●●●●●○○○○○` 🟣 品红色     |
| `arrow`   | `▸▸▸▸▸▹▹▹▹▹` 🔵 蓝色       |

## Spinner 样式

| 样式     | 帧                |
|----------|-------------------|
| `dots`   | ⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ |
| `line`   | - \ \| /          |
| `circle` | ◐ ◓ ◑ ◒          |
| `bounce` | ⠁ ⠂ ⠄ ⠂          |
| `arrows` | ← ↑ → ↓          |
| `grow`   | ▏ ▎ ▍ ▌ ▋ ▊ ▉ █  |
| `moon`   | 🌑🌒🌓🌔🌕🌖🌗🌘   |

## 自定义颜色

```python
# 颜色名
Bar(100, color="cyan", label="青色进度条")

# 任意 hex 颜色
Bar(100, color="#FF5733", label="橙色进度条")
Bar(100, color="#00FF99", label="薄荷绿进度条")
```

## 自定义字符

```python
Bar(100, fill="▓", empty="▒")
Bar(100, fill="=", empty="-")
Bar(100, fill="●", empty="○", color="#FF69B4")
```

## 生成器与迭代器

`track()` 可以包装任何拥有 `len()` 的对象。对于生成器,需要传入 `total=`:

```python
def my_generator():
    for i in range(1000):
        yield i

for item in track(my_generator(), total=1000, label="Generating"):
    process(item)
```

## 在非 TTY 环境中的行为

当输出被重定向到文件或在 CI 中运行时,flashbar 会自动检测并保持安静 —— 只输出最终行,且不带任何转义代码:

```bash
python myscript.py 2> log.txt    # log.txt 保持干净
python myscript.py 2>&1 | tee    # 没有乱码输出
```

## API 参考

### 进度条

#### `Bar(total, **options)`

| 参数         | 类型   | 默认值      | 说明                                |
|--------------|--------|-------------|-------------------------------------|
| `total`      | int    | 必填        | 总步数                              |
| `width`      | int    | `40`        | 进度条字符宽度                      |
| `theme`      | str    | `"default"` | 主题名称                            |
| `label`      | str    | `""`        | 进度条前的文字                      |
| `color`      | str    | `None`      | 覆盖颜色(名称或 hex)              |
| `fill`       | str    | `None`      | 覆盖填充字符                        |
| `empty`      | str    | `None`      | 覆盖空白字符                        |
| `show_eta`   | bool   | `True`      | 显示预计剩余时间                    |
| `show_speed` | bool   | `False`     | 显示每秒处理数                      |
| `smooth`     | bool   | `None`      | 亚字符渲染。None 为自动             |

方法:`.update(step=1)`,`.set(value)`,context manager。

#### `track(iterable, **options)`

参数与 `Bar` 相同,加上 `total=` 用于没有 `len()` 的迭代对象。

#### `Spinner(label, **options)`

| 参数    | 类型  | 默认值   | 说明                |
|---------|-------|----------|---------------------|
| `label` | str   | `""`     | spinner 旁边的文字  |
| `style` | str   | `"dots"` | spinner 动画样式    |
| `color` | str   | `"cyan"` | 颜色(名称或 hex)  |
| `speed` | float | `0.08`   | 每帧间隔秒数        |

方法:`.start()`,`.stop(final_text=None)`,context manager。

### 美观输出

#### `panel(text, **options) -> str`

| 参数      | 类型 | 默认值      | 说明                                       |
|-----------|------|-------------|--------------------------------------------|
| `text`    | str  | 必填        | 主体内容(可包含换行符)                   |
| `title`   | str  | `None`      | 顶部边框中可选的标题                       |
| `color`   | str  | `None`      | 边框颜色(名称或 hex)                     |
| `width`   | int  | `None`      | 总宽度。None 为自动适应                    |
| `style`   | str  | `"rounded"` | rounded, square, double, heavy, ascii     |
| `padding` | int  | `1`         | 盒内水平填充                               |

#### `rule(label="", width=None, color=None) -> str`

水平分隔线。空 `label` 表示纯分隔线。

#### 状态指示器(返回 `str`)

```python
success("ok")  # ✓ ok
error("no")    # ✗ no
warn("hmm")    # ⚠ hmm
info("fyi")    # ℹ fyi
```

#### `print_panel(text, title=None, color=None, file=None, **kwargs)`

便捷函数:构建并打印 panel。在非 TTY 环境中自动剥离样式。

## 许可证

MIT
