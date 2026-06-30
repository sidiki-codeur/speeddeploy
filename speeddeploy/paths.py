"""Path formatting helpers."""

from __future__ import annotations

from pathlib import Path


def as_posix_text(value: Path | str) -> str:
    """Render a path-like value with forward slashes for YAML and templates."""
    return str(value).replace("\\", "/")
