"""Shared CSS loader — reads .css files from src/templates/ for inline embedding."""

from pathlib import Path

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _read_css(filename):
    return (_TEMPLATES_DIR / filename).read_text(encoding="utf-8")


SHARED_CSS = _read_css("base.css")
COMPACT_CSS = _read_css("compact.css")
