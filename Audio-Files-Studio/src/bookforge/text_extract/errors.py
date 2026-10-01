"""Errors raised by the text extraction package."""

from __future__ import annotations


class ExtractionError(Exception):
    """Raised when a document cannot be extracted to text."""