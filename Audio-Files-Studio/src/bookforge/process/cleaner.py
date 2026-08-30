"""Text cleaning and normalization for audiobook processing."""

from __future__ import annotations

import re

import inflect  # add to requirements.txt

p = inflect.engine()


def clean_text(text: str) -> str:
    """
    Clean and normalize text for TTS processing.

    Handles:
    - OCR artifacts (weird spacing, broken words)
    - Excessive whitespace
    - Page numbers and headers/footers
    - Special characters
    - Number expansion
    - Abbreviation expansion
    """
    # Remove page numbers (standalone numbers on lines)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

    # Remove common OCR artifacts
    text = text.replace("- ", "")  # Hyphenated line breaks
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)  # "hy- phen" → "hyphen"

    # Fix broken spacing from OCR (e.g., "T h e" → "The")
    text = re.sub(r"\b([A-Z])\s+([a-z])\s+([a-z])\b", r"\1\2\3", text)

    # Remove headers/footers (repeated text patterns)
    lines = text.split("\n")
    line_counts = {}
    for line in lines:
        stripped = line.strip()
        if len(stripped) > 10:
            line_counts[stripped] = line_counts.get(stripped, 0) + 1
    repeated = {line for line, count in line_counts.items() if count > 3}
    lines = [line for line in lines if line.strip() not in repeated]
    text = "\n".join(lines)

    # Normalise whitespace
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    # Fix common punctuation issues
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)  # Remove space before punctuation
    text = re.sub(r"([.,;:!?])([A-Za-z])", r"\1 \2", text)  # Add space after punctuation

    # Remove citation markers that sound bad when read aloud
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\(see [^)]+\)", "", text)

    # Clean up quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(""", "'").replace(""", "'")

    # ---- New big wins ----
    # 1. Expand numbers (e.g., "42" → "forty-two")
    def replace_number(match):
        num = match.group(0)
        try:
            return p.number_to_words(num)
        except:
            return num

    text = re.sub(r"\b\d+\b", replace_number, text)

    # 2. Expand common abbreviations
    abbrev_map = {
        r"\bDr\.\b": "Doctor",
        r"\bMr\.\b": "Mister",
        r"\bMrs\.\b": "Misses",
        r"\bMs\.\b": "Miss",
        r"\bSt\.\b": "Saint",
        r"\bAve\.\b": "Avenue",
        r"\bRd\.\b": "Road",
        r"\bBlvd\.\b": "Boulevard",
        r"\bSr\.\b": "Senior",
        r"\bJr\.\b": "Junior",
        r"\bvs\.\b": "versus",
        r"\betc\.\b": "et cetera",
        r"\bN\.B\.\b": "Note well",
        r"\bi\.e\.\b": "that is",
        r"\be\.g\.\b": "for example",
    }
    for pattern, replacement in abbrev_map.items():
        text = re.sub(pattern, replacement, text)

    # 3. Handle ellipsis (… or ...) – replace with three periods with a space after
    text = re.sub(r"…", "...", text)
    text = re.sub(r"\.\.\.", "... ", text)

    # 4. Ensure sentence boundaries have a space after them
    text = re.sub(r"([.!?])([A-Z])", r"\1 \2", text)

    # Final cleanup
    text = text.strip()
    return text
