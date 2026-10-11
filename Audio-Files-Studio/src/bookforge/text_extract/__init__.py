"""Document text extraction and TTS-friendly cleanup."""

from __future__ import annotations

from .errors import ExtractionError
from .extractor import SUPPORTED_EXTENSIONS, extract
from .cleanup import all_rules, apply_llm_verdicts, clean, clean_debug, default_enabled_keys

__all__ = [
    "ExtractionError",
    "SUPPORTED_EXTENSIONS",
    "extract",
    "all_rules",
    "apply_llm_verdicts",
    "clean",
    "clean_debug",
    "default_enabled_keys",
]