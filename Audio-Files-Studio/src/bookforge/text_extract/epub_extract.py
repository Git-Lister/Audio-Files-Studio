"""EPUB extraction via ebooklib + BeautifulSoup."""

from __future__ import annotations

from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from .errors import ExtractionError


def extract(path: Path) -> str:
    try:
        book = epub.read_epub(str(path))
    except Exception as e:
        raise ExtractionError(f"EPUB open failed: {e}") from e

    parts: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        content = item.get_content()
        try:
            soup = BeautifulSoup(content, "lxml")
        except Exception:
            continue

        for bad in soup(["script", "style", "nav", "footer"]):
            bad.decompose()

        title: str | None = None
        for tag in ("h1", "h2", "h3"):
            heading = soup.find(tag)
            if heading:
                text = heading.get_text(strip=True)
                if text:
                    title = text
                    break

        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
        body = "\n\n".join(p for p in paragraphs if p)
        if not body:
            body = soup.get_text(separator="\n", strip=True)

        if not body:
            continue

        if title:
            parts.append(f"# {title}\n\n{body}")
        else:
            parts.append(body)

    return "\n\n".join(parts)