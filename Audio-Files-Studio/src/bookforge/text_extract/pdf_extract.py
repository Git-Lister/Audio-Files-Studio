"""PDF extraction via pdfminer.six."""

from __future__ import annotations

from pathlib import Path

from pdfminer.high_level import extract_text

from .errors import ExtractionError


def extract(path: Path) -> str:
    try:
        return extract_text(str(path))
    except Exception as e:
        raise ExtractionError(f"PDF extraction failed: {e}") from e