"""Shared constants and utilities for output generators."""

from common.shared_styles import COMPACT_CSS
from common.shared_styles import SHARED_CSS as _BASE_CSS

# Combined CSS for output pages (base + compact overrides)
SHARED_CSS = _BASE_CSS + COMPACT_CSS

# Presentation threshold: items within +/-N% of real cost are "fair priced"
EFFICIENCY_THRESHOLD_PCT = 10


def get_nav_html(active: str) -> str:
    """Generate navigation HTML."""
    pages = [
        ("axioms_table.html", "Axioms"),
        ("items_table.html", "Items"),
        ("interactive_chart.html", "Chart"),
    ]
    links = []
    for href, label in pages:
        cls = "active" if href == active else ""
        links.append(f'<a href="{href}" class="{cls}">{label}</a>')
    return f'<div class="nav">{" ".join(links)}</div>'
