"""Plain text ingestion with chapter detection."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import List

from ..process.chapter_detector import ChapterDetector


@dataclass
class BookText:
    title: str
    chapters: List[str]
    chapter_titles: List[str] = None  # Store detected chapter titles


def load_txt(
    path: Path,
    chapter_strategy: str = "auto",
    min_confidence: float = 0.5
) -> BookText:
    """Load plain text with automatic chapter detection.
    
    Args:
        path: Path to text file
        chapter_strategy: Detection method (auto, markdown, structured, 
                         heuristic, paragraph, none)
        min_confidence: Minimum confidence threshold for boundaries
    
    Returns:
        BookText with detected chapters
    """
    text = path.read_text(encoding="utf-8", errors="ignore")

    detector = ChapterDetector()
    boundaries = detector.detect(
        text,
        strategy=chapter_strategy,
        min_confidence=min_confidence
    )

    if not boundaries:
        # Fallback: treat as single chapter
        return BookText(
            title=path.stem,
            chapters=[text],
            chapter_titles=["Full Text"]
        )

    # Split text at detected boundaries
    lines = text.split('\n')
    chapters = []
    chapter_titles = []

    for i, boundary in enumerate(boundaries):
        start = boundary.line_index
        end = boundaries[i + 1].line_index if i + 1 < len(boundaries) else len(lines)

        chapter_text = '\n'.join(lines[start:end])
        chapters.append(chapter_text)
        
        # Use detected title or generate fallback
        title = boundary.title or f"Chapter {i + 1}"
        chapter_titles.append(title)

    return BookText(
        title=path.stem,
        chapters=chapters,
        chapter_titles=chapter_titles
    )
