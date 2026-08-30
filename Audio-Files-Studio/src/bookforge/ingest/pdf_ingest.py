"""PDF ingestion for BookForge (simple text extraction)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from pdfminer.high_level import extract_text  # type: ignore[import]


@dataclass
class BookText:
    """Simple representation of a book's text content."""
    title: str
    chapters: List[str]


def load_pdf(path: Path) -> BookText:
    """Extract plain text from a PDF and treat it as a single chapter.

    This is a simple baseline using pdfminer.six extract_text().
    More advanced layout-aware extraction can come later.
    """
    text = extract_text(str(path))
    title = path.stem
    return BookText(title=title, chapters=[text])
