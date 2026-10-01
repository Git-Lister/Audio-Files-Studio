"""DOCX extraction via python-docx."""

from __future__ import annotations

from pathlib import Path

from docx import Document

from .errors import ExtractionError


def extract(path: Path) -> str:
    try:
        doc = Document(str(path))
    except Exception as e:
        raise ExtractionError(f"DOCX open failed: {e}") from e
    paragraphs = [p.text for p in doc.paragraphs]
    # Join with double newline so paragraph structure survives into cleanup.
    return "\n\n".join(paragraphs)