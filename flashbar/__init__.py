"""flashbar — lightweight, pretty progress bars for the terminal."""

__version__ = "1.0.0"

from .bar import Bar, track, THEMES, NAMED_COLORS, resolve_color
from .spinner import Spinner, SPINNER_STYLES

__all__ = [
    "Bar",
    "track",
    "Spinner",
    "THEMES",
    "NAMED_COLORS",
    "SPINNER_STYLES",
]
