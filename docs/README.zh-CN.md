# ⚡ flashbar

🌐 [English](../README.md) · **简体中文** · [Русский](README.ru.md)

![README: generated with AI](https://img.shields.io/badge/README-generated%20with%20AI-6f42c1)

适用于 Python 3.8+ 的轻量级进度条和格式化 CLI 输出库。

<p align="center">
  <img src="../demo.gif" alt="flashbar 演示" width="600">
</p>

## 安装

```bash
pip install flashbar
```

## 更新检查

进度条或旋转指示器在交互式终端中成功结束后，flashbar 会检查 PyPI
上的新版本。结果缓存 7 天，因此不会在每次运行时请求或提示：

```text
ℹ  flashbar 1.4.0 is available (you have 1.3.0).
Run: pip install -U flashbar
```

网络或缓存错误会被静默忽略。重定向输出、`CI`、GitHub Actions 和常见
JSON 输出参数下不会检查。如果宿主 CLI 接受 `--no-update-check`，flashbar
会识别该参数。通用的关闭方式是设置 `FLASHBAR_NO_UPDATE_CHECK=1`。

只使用格式化辅助函数的应用，可以在主命令完成后显式调用：

```python
from flashbar import maybe_notify

maybe_notify()
```

其他机器可读输出模式应跳过此调用。

## 快速开始

```python
from flashbar import track
import time

for item in track(range(100), label="Downloading"):
    time.sleep(0.02)
```

## 格式化输出

通过几个小函数构建样式化的 CLI 输出:

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

`panel()`、`rule()` 和状态函数可传入 `plain=True`,以移除 ANSI 并使用 ASCII 装饰。此模式也会移除用户文本中嵌套的 ANSI 序列:

```python
print(success("Tests passed", plain=True))  # [OK] Tests passed
print(rule("Build log", width=32, plain=True))
```

默认 `plain=None` 时,仅在 stdout 是编码兼容的 TTY 时使用 Unicode 样式。传入 `plain=False` 可强制使用样式。

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

### 单位和动态状态

设置 `unit` 后会显示已完成量和总量。`unit_scale=True` 对字节使用二进制
单位，对其他值使用十进制单位：

```python
bar = Bar(file_size, label="Downloading", unit="B",
          unit_scale=True, show_speed=True)
# Downloading [████░░] 42% 4.2 MiB / 10.0 MiB 1.3 MiB/s
```

任务运行时可以更新标签和附加字段：

```python
bar.set_label("Compiling main.py")
bar.set_postfix(files=42, errors=0)
bar.set_postfix()  # 清除
```

### 未知总量

总量未知时使用 `total=None`。每次 `update()` 都会移动不定进度动画并增加
计数。知道总量后，可以让同一个进度条切换到百分比和 ETA：

```python
bar = Bar(None, label="Scanning", unit="files")
bar.update()
bar.update()
bar.set_total(1500)
```

### 临时进度条

`transient=True` 会在完成后从终端移除进度条，重定向输出时也不会留下
最终行：

```python
with Bar(100, transient=True) as bar:
    run_task(bar)
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

自定义 `fill` 和 `empty` 必须各自正好占用一个终端单元格。

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
| `total`      | int 或 None | 必填   | 总步数；None 表示未知               |
| `width`      | int    | `40`        | 进度条字符宽度                      |
| `theme`      | str    | `"default"` | 主题名称                            |
| `label`      | str    | `""`        | 进度条前的文字                      |
| `color`      | str    | `None`      | 覆盖颜色(名称或 hex)              |
| `fill`       | str    | `None`      | 覆盖填充字符                        |
| `empty`      | str    | `None`      | 覆盖空白字符                        |
| `show_eta`   | bool   | `True`      | 显示预计剩余时间                    |
| `show_speed` | bool   | `False`     | 显示每秒处理数                      |
| `smooth`     | bool   | `None`      | 亚字符渲染。None 为自动             |
| `unit`       | str    | `None`      | 计数和速度使用的单位                |
| `unit_scale` | bool   | `False`     | 字节使用 KiB/MiB，其他单位使用 k/M  |
| `transient`  | bool   | `False`     | 完成后移除输出                      |

方法：`.update(step=1)`、`.set(value)`、`.set_total(total)`、
`.set_label(label)`、`.set_postfix(**fields)` 和 context manager。负步长会被
拒绝。减小 `.set()` 的值或增加总量会重新打开已完成的进度条并重启计时器。

#### `track(iterable, **options)`

参数与 `Bar` 相同,加上 `total=` 用于没有 `len()` 的迭代对象。

#### `Spinner(label, **options)`

| 参数    | 类型  | 默认值   | 说明                |
|---------|-------|----------|---------------------|
| `label` | str   | `""`     | spinner 旁边的文字  |
| `style` | str   | `"dots"` | spinner 动画样式    |
| `color` | str   | `"cyan"` | 颜色(名称或 hex)  |
| `speed` | float | `0.08`   | 每帧间隔的正有限秒数 |

方法:`.start()`,`.stop(final_text=None)`,context manager。

### 格式化输出

#### `panel(text, **options) -> str`

| 参数      | 类型 | 默认值      | 说明                                       |
|-----------|------|-------------|--------------------------------------------|
| `text`    | str  | 必填        | 主体内容(可包含换行符)                   |
| `title`   | str  | `None`      | 顶部边框中可选的标题                       |
| `color`   | str  | `None`      | 边框颜色(名称或 hex)                     |
| `width`   | int  | `None`      | 总宽度。None 为自动适应                    |
| `style`   | str  | `"rounded"` | rounded, square, double, heavy, ascii     |
| `padding` | int  | `1`         | 盒内水平填充                               |
| `plain`   | bool 或 None | `None` | 自动检测;True = ASCII,False = 样式 |

#### `rule(label="", width=None, color=None, plain=None) -> str`

水平分隔线。空 `label` 表示纯分隔线,可见宽度始终与 `width` 一致。`plain=None` 时仅在 `sys.stdout` 为 TTY 时使用样式;`plain=False` 可强制启用样式。

#### 状态指示器(返回 `str`)

状态函数也使用 `plain=None` 自动检测。`plain=False` 强制彩色输出,`plain=True` 输出可移植的 ASCII 文本。

```python
success("ok")  # ✓ ok
error("no")    # ✗ no
warn("hmm")    # ⚠ hmm
info("fyi")    # ℹ fyi

success("ok", plain=True)  # [OK] ok
```

#### `print_panel(text, title=None, color=None, file=None, **kwargs)`

构建并打印 panel。非 TTY 默认使用紧凑输出。`plain=True` 保留完整 ASCII 面板,`plain=False` 强制输出带样式的面板。

## 许可证

MIT
