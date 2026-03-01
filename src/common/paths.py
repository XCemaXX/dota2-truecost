"""Centralized path helper for the 2parser project."""

from pathlib import Path


def get_paths(project_root):
    """Return a dict of standard project paths given the project root."""
    root = Path(project_root)
    return {
        "project_root": root,
        "src": root / "src",
        "output": root / "output",
        "data": root / "data",
        "docs": root / "docs",
    }
