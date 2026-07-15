# ⚡ flashbar

🌐 [English](../README.md) · [简体中文](README.zh-CN.md) · **Русский**

![README: generated with AI](https://img.shields.io/badge/README-generated%20with%20AI-6f42c1)

`flashbar` — небольшой Python-пакет для индикаторов прогресса и форматирования CLI-вывода.
Работает с Python 3.8+ и не требует внешних зависимостей.

<p align="center">
  <img src="../demo.gif" alt="Демонстрация flashbar" width="600">
</p>

## Установка

```bash
pip install flashbar
```

## Быстрый старт

```python
from flashbar import track
import time

for item in track(range(100), label="Downloading"):
    time.sleep(0.02)
```

## Форматирование вывода

Для рамок, разделителей и статусных сообщений есть несколько отдельных функций:

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

Вывод:

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

### Стили панелей

Доступно пять стилей рамки:

```python
panel("body", style="rounded")  # ╭ ╮ ╰ ╯  (по умолчанию)
panel("body", style="square")   # ┌ ┐ └ ┘
panel("body", style="double")   # ╔ ╗ ╚ ╝
panel("body", style="heavy")    # ┏ ┓ ┗ ┛
panel("body", style="ascii")    # + + + +
```

Размер автоматически подгоняется под содержимое; также можно передать `width=N` для фиксированной ширины. Поддерживаются произвольный `color` (имя или hex) и `padding`.

`plain=True` у `panel()`, `rule()` и статусных функций убирает ANSI-коды и использует ASCII-оформление. Вложенные ANSI-коды в тексте также удаляются:

```python
print(success("Tests passed", plain=True))  # [OK] Tests passed
print(rule("Build log", width=32, plain=True))
```

При стандартном `plain=None` Unicode-оформление используется только для TTY с подходящей кодировкой. `plain=False` принудительно включает оформление.

### Разделитель

Горизонтальная линия с необязательной меткой по центру:

```python
print(rule())                         # линия на всю ширину
print(rule("Section 1"))              # метка по центру
print(rule("Done", color="green"))    # цветная линия
```

### Помощник печати

Если не хочется самостоятельно вызывать `print()`:

```python
from flashbar import print_panel

print_panel("Connection failed", title="Error", color="red")
```

Если вывод не является TTY (например, в логах или CI), ANSI-оформление отключается.

## Индикатор прогресса

```python
from flashbar import Bar

bar = Bar(100, label="Processing", theme="green")
for i in range(100):
    bar.update()

# или сразу перейти к конкретному значению
bar = Bar(100)
bar.set(50)  # перейти к 50%
bar.set(100) # готово
```

### Контекстный менеджер

Автоматически завершает полосу при выходе, даже при исключении:

```python
with Bar(100, theme="retro", label="Building") as bar:
    for i in range(100):
        do_work()
        bar.update()
```

### ETA и скорость

```python
# ETA включена по умолчанию
bar = Bar(1000, label="Training", show_eta=True)

# также показывать элементы в секунду
bar = Bar(1000, label="Training", show_speed=True)
```

### Плавная отрисовка

Отрисовка с точностью до долей символа делает полосы намного плавнее. Она включается автоматически для символа заполнения `█`, но её можно задать явно:

```python
# всегда плавно
Bar(100, smooth=True)

# всегда классически
Bar(100, smooth=False)
```

## Спиннер

Для задач, общий объём которых неизвестен:

```python
from flashbar import Spinner

with Spinner("Loading data...", style="dots"):
    load_big_file()

# ручное управление
sp = Spinner("Thinking...", style="circle", color="magenta")
sp.start()
result = heavy_computation()
sp.stop("Done!")
```

## Темы

На демонстрационной GIF-анимации выше можно увидеть все темы с реальными цветами.

```python
from flashbar import Bar

for name in ["default", "green", "red", "retro", "minimal", "slim", "dots", "arrow"]:
    bar = Bar(30, theme=name, label=f"{name:8s}")
    for _ in range(30):
        bar.update()
```

| Тема      | Вид                        |
|-----------|----------------------------|
| `default` | `█████░░░░░` 🔵 синий       |
| `green`   | `█████░░░░░` 🟢 зелёный     |
| `red`     | `█████░░░░░` 🔴 красный      |
| `retro`   | `#####.....` 🟡 жёлтый     |
| `minimal` | `─────     ` ⚪ белый      |
| `slim`    | `━━━━━╺╺╺╺╺` 🔵 голубой    |
| `dots`    | `●●●●●○○○○○` 🟣 пурпурный |
| `arrow`   | `▸▸▸▸▸▹▹▹▹▹` 🔵 синий       |

## Стили спиннера

| Стиль    | Кадры            |
|----------|-------------------|
| `dots`   | ⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ |
| `line`   | - \ \| /          |
| `circle` | ◐ ◓ ◑ ◒          |
| `bounce` | ⠁ ⠂ ⠄ ⠂          |
| `arrows` | ← ↑ → ↓          |
| `grow`   | ▏ ▎ ▍ ▌ ▋ ▊ ▉ █  |
| `moon`   | 🌑🌒🌓🌔🌕🌖🌗🌘   |

## Цвета

```python
# именованный цвет
Bar(100, color="cyan", label="Cyan bar")

# любой hex-цвет
Bar(100, color="#FF5733", label="Orange bar")
Bar(100, color="#00FF99", label="Mint bar")
```

## Символы заполнения

```python
Bar(100, fill="▓", empty="▒")
Bar(100, fill="=", empty="-")
Bar(100, fill="●", empty="○", color="#FF69B4")
```

Значения `fill` и `empty` должны занимать ровно одну ячейку терминала каждое.

## Генераторы и итераторы

`track()` работает со всем, у чего есть `len()`. Для генераторов передайте `total=`:

```python
def my_generator():
    for i in range(1000):
        yield i

for item in track(my_generator(), total=1000, label="Generating"):
    process(item)
```

## Вывод без TTY

При перенаправлении вывода в файл или запуске в CI flashbar печатает только итоговую строку без ANSI-последовательностей:

```bash
python myscript.py 2> log.txt    # log.txt остаётся чистым
python myscript.py 2>&1 | tee    # без искажённого вывода
```

## Справочник API

### Прогресс

#### `Bar(total, **options)`

| Параметр    | Тип    | По умолчанию | Описание                           |
|-------------|--------|----------------|------------------------------------|
| `total`      | int    | обязателен    | Число шагов                         |
| `width`      | int    | `40`           | Ширина полосы в символах            |
| `theme`      | str    | `"default"`    | Имя темы                           |
| `label`      | str    | `""`           | Текст перед полосой                   |
| `color`      | str    | `None`         | Переопределение цвета (имя или hex)    |
| `fill`       | str    | `None`         | Символ заполнения                    |
| `empty`      | str    | `None`         | Символ пустой части                   |
| `show_eta`   | bool   | `True`         | Показывать оценку оставшегося времени |
| `show_speed` | bool   | `False`        | Показывать элементы в секунду          |
| `smooth`     | bool   | `None`         | Подсимвольная отрисовка; None = авто    |

Методы: `.update(step=1)`, `.set(value)`, контекстный менеджер. Отрицательный шаг запрещён. Вызов `.set()` со значением меньше максимума повторно открывает завершённый бар и перезапускает таймер.

#### `track(iterable, **options)`

Те же параметры, что у `Bar`, плюс `total=` для итерируемых объектов без `len()`.

#### `Spinner(label, **options)`

| Параметр | Тип   | По умолчанию | Описание                    |
|----------|-------|----------------|-----------------------------|
| `label`  | str   | `""`           | Текст рядом со спиннером       |
| `style`  | str   | `"dots"`       | Стиль анимации спиннера        |
| `color`  | str   | `"cyan"`       | Цвет (имя или hex)           |
| `speed`  | float | `0.08`         | Положительное конечное число секунд между кадрами |

Методы: `.start()`, `.stop(final_text=None)`, контекстный менеджер.

### Форматирование вывода

#### `panel(text, **options) -> str`

| Параметр | Тип | По умолчанию | Описание                                      |
|----------|-----|----------------|-----------------------------------------------|
| `text`   | str | обязателен    | Содержимое; может включать переносы строк       |
| `title`  | str | `None`         | Необязательный заголовок в верхней границе             |
| `color`  | str | `None`         | Цвет границы (имя или hex)                       |
| `width`  | int | `None`         | Общая ширина; None = автоподгонка под содержимое    |
| `style`  | str | `"rounded"`    | rounded, square, double, heavy, ascii         |
| `padding`| int | `1`            | Горизонтальные отступы внутри рамки                 |
| `plain`  | bool или None | `None` | Автоопределение; True = ASCII, False = оформление |

#### `rule(label="", width=None, color=None, plain=None) -> str`

Горизонтальный разделитель. Пустой `label` создаёт обычную линию. Видимая ширина всегда равна `width`. При `plain=None` оформление включается только для TTY; `plain=False` включает его принудительно.

#### Индикаторы состояния (возвращают `str`)

Статусные функции также автоматически определяют TTY при `plain=None`. Для принудительного цвета используйте `plain=False`, для ASCII — `plain=True`.

```python
success("ok")  # ✓ ok
error("no")    # ✗ no
warn("hmm")    # ⚠ hmm
info("fyi")    # ℹ fyi

success("ok", plain=True)  # [OK] ok
```

#### `print_panel(text, title=None, color=None, file=None, **kwargs)`

Создаёт и печатает панель. Для не-TTY вывод по умолчанию компактный. `plain=True` сохраняет полную ASCII-панель, а `plain=False` принудительно включает оформленную панель.

## Лицензия

MIT
