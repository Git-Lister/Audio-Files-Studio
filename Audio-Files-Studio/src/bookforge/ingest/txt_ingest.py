"""Plain text ingestion with chapter detection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from ..process.chapter_detector import ChapterDetector


@dataclass
class BookText:
    title: str
    chapters: List[str]
    chapter_titles: List[str] = None  # Store detected chapter titles


def _strip_front_matter(text: str) -> str:
    """Remove common front matter like copyright, table of contents."""
    # Simple heuristic: remove everything before first chapter heading like "Chapter 1"
    # We'll rely on chapter detector, but we can do a quick clean.
    # For now, just return text as is; detector will handle.
    return text


def load_txt(path: Path, chapter_strategy: str = "auto", min_confidence: float = 0.5) -> BookText:
    """Load plain text with automatic chapter detection."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    # Optional: strip front matter
    text = _strip_front_matter(text)

    detector = ChapterDetector()
    boundaries = detector.detect(text, strategy=chapter_strategy, min_confidence=min_confidence)

    if not boundaries:
        return BookText(title=path.stem, chapters=[text], chapter_titles=["Full Text"])

    lines = text.split("\n")
    chapters = []
    chapter_titles = []

    for i, boundary in enumerate(boundaries):
        start = boundary.line_index
        end = boundaries[i + 1].line_index if i + 1 < len(boundaries) else len(lines)
        chapter_text = "\n".join(lines[start:end])
        chapters.append(chapter_text)
        title = boundary.title or f"Chapter {i + 1}"
        chapter_titles.append(title)

    return BookText(title=path.stem, chapters=chapters, chapter_titles=chapter_titles)
