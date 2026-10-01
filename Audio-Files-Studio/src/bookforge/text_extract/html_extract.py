"""HTML extraction via BeautifulSoup + lxml."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from .errors import ExtractionError


def extract(path: Path) -> str:
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise ExtractionError(f"HTML read failed: {e}") from e
    return extract_from_html_string(html)


def extract_from_html_string(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for bad in soup(["script", "style", "nav", "footer", "header", "aside"]):
        bad.decompose()

    parts: list[str] = []
    for el in soup.find_all(["h1", "h2", "h3", "p"]):
        text = el.get_text(strip=True)
        if not text:
            continue
        if el.name in ("h1", "h2"):
            parts.append(f"# {text}")
        else:
            parts.append(text)
    return "\n\n".join(parts)