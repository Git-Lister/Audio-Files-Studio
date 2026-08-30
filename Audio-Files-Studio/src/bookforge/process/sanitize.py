"""Text sanitization for TTS engines – now with robust footnote removal."""

from __future__ import annotations

import re
import unicodedata


def sanitise_for_tts(text: str) -> str:
    """
    Sanitize text for TTS synthesis.

    - Remove/replace characters that cause TTS errors
    - Expand abbreviations for better pronunciation
    - Add prosody hints (pauses) for natural rhythm
    - Remove footnote/citation markers that sound bad when read aloud
    """
    # Normalize unicode
    text = unicodedata.normalize("NFKC", text)

    # Remove zero‑width and control characters
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")
    text = text.replace("\r", "")

    # Replace em/en dashes
    text = text.replace("—", " - ")
    text = text.replace("–", " - ")

    # -------- Remove footnote/citation markers --------
    # Already handled by cleaner.py: [1], [23], (see ...) – but we double down

    # 1. Bracketed numeric citations (e.g., [1], [1,2], [1-3])
    text = re.sub(r"\[\s*\d+(?:\s*[,-]\s*\d+)*\s*\]", "", text)

    # 2. Superscript numbers that lost formatting: a digit attached to a word
    #    Only if the word ends with a letter and the digit is 1‑4 chars, typical footnote.
    text = re.sub(r"(?<=[a-zA-Z])(\d{1,4})(?=[\s.,;:!?]|$)", "", text)

    # 3. A small number directly after a period or comma with no space – likely a citation
    #    e.g., "end.12" → remove the number
    text = re.sub(r"(?<=[.,;:!?])(\d{1,4})(?=[\s.,;:!?]|$)", "", text)

    # 4. Bare numbers that are likely footnote references at the end of a sentence.
    #    Match a number that is preceded by a letter/punctuation, then a space, then the
    #    number, then a period or end of string.
    text = re.sub(r"(?<=[a-zA-Z.!?]) (\d{1,3})\.(?=\s|$)", ".", text)

    # 5. Remove standalone page numbers (already in cleaner, but safe to repeat)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

    # -------- Abbreviations --------
    text = text.replace("e.g.", "for example")
    text = text.replace("E.g.", "For example")
    text = text.replace("i.e.", "that is")
    text = text.replace("I.e.", "That is")
    text = text.replace("etc.", "et cetera")
    text = text.replace("vs.", "versus")
    text = text.replace("c.f.", "compare")
    text = text.replace("et al.", "and others")
    text = text.replace("ibid.", "same source")
    text = text.replace("op. cit.", "previously cited")

    # -------- Prosody hints --------
    # Double space after sentence endings for a subtle pause
    text = re.sub(r"([.!?])\s+", r"\1  ", text)
    # Preserve paragraph breaks
    text = re.sub(r"\n\n+", "\n\n", text)

    # Final whitespace cleanup
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()

    # Safety: remove any remaining surrogates
    text = text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")

    return text
