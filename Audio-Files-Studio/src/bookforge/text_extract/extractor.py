"""Dispatch document extraction by file extension."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .docx_extract import extract as _extract_docx
from .epub_extract import extract as _extract_epub
from .errors import ExtractionError
from .html_extract import extract as _extract_html
from .pdf_extract import extract as _extract_pdf
from .txt_extract import extract as _extract_txt

_EXTRACTORS: dict[str, Callable[[Path], str]] = {
    ".txt": _extract_txt,
    ".md": _extract_txt,
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".epub": _extract_epub,
    ".html": _extract_html,
    ".htm": _extract_html,
}

SUPPORTED_EXTENSIONS: tuple[str, ...] = tuple(sorted(_EXTRACTORS.keys()))


def extract(path: Path) -> str:
    """Extract raw text from a document. Raises ExtractionError on failure.

    Returns an empty string if the document contains no extractable text
    (e.g. a scanned PDF). Callers should treat empty output as a warning.
    """
    ext = path.suffix.lower()
    fn = _EXTRACTORS.get(ext)
    if fn is None:
        supported = ", ".join(SUPPORTED_EXTENSIONS)
        raise ExtractionError(
            f"Unsupported file type: {ext}. Supported: {supported}"
        )
    try:
        return fn(path)
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"Failed to extract {path.name}: {e}") from e