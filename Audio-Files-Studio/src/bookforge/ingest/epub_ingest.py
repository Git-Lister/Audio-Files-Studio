"""EPUB ingestion for BookForge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup  # add to dependencies if you like


@dataclass
class BookText:
    """Simple representation of a book's text content."""

    title: str
    chapters: List[str]


def _extract_doc_text(doc: epub.EpubHtml) -> str:
    """Extract visible paragraph text from an EPUB document."""
    soup = BeautifulSoup(doc.content, "html.parser")
    # simple heuristic: join all <p> text
    paragraphs = [p.get_text(separator=" ", strip=True) for p in soup.find_all("p")]
    return "\n\n".join(p for p in paragraphs if p)


def load_epub(path: Path) -> BookText:
    """Load an EPUB file into BookText (chapters from spine order)."""
    book = epub.read_epub(str(path))
    metadata_title = book.get_metadata("DC", "title")
    if metadata_title and metadata_title[0]:
        title = metadata_title[0][0]
    else:
        title = path.stem

    chapters: List[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        text = _extract_doc_text(item)
        if text.strip():
            chapters.append(text)

    if not chapters:
        chapters = [title]

    return BookText(title=title, chapters=chapters)
