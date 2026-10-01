"""Plain text and markdown extraction (pass-through)."""

from __future__ import annotations

from pathlib import Path


def extract(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")