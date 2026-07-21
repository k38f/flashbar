"""flashbar — lightweight, pretty progress bars for the terminal."""

__version__ = "1.4.0"

from .bar import Bar, NAMED_COLORS, THEMES, resolve_color, track
from .pretty import error, info, panel, print_panel, rule, success, warn
from .spinner import SPINNER_STYLES, Spinner
from .update_check import maybe_notify

__all__ = [
    # progress
    "Bar",
    "track",
    "Spinner",
    # pretty output
    "panel",
    "print_panel",
    "rule",
    "success",
    "error",
    "warn",
    "info",
    # constants & helpers
    "THEMES",
    "NAMED_COLORS",
    "SPINNER_STYLES",
    "resolve_color",
    "maybe_notify",
]
