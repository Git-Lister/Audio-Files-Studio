"""Text cleaning and normalization for audiobook processing."""

from __future__ import annotations

import re


def clean_text(text: str) -> str:
    """
    Clean and normalize text for TTS processing.
    
    Handles:
    - OCR artifacts (weird spacing, broken words)
    - Excessive whitespace
    - Page numbers and headers/footers
    - Special characters
    """
    # Remove page numbers (standalone numbers on lines)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    
    # Remove common OCR artifacts
    text = text.replace('- ', '')  # Hyphenated line breaks
    text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)  # "hy- phen" → "hyphen"
    
    # Fix broken spacing from OCR (e.g., "T h e" → "The")
    text = re.sub(r'\b([A-Z])\s+([a-z])\s+([a-z])\b', r'\1\2\3', text)
    
    # Remove headers/footers (repeated text patterns)
    # Simple heuristic: lines that repeat verbatim multiple times
    lines = text.split('\n')
    line_counts = {}
    for line in lines:
        stripped = line.strip()
        if len(stripped) > 10:  # Only track substantial lines
            line_counts[stripped] = line_counts.get(stripped, 0) + 1
    
    # Remove lines that appear more than 3 times (likely headers/footers)
    repeated = {line for line, count in line_counts.items() if count > 3}
    lines = [line for line in lines if line.strip() not in repeated]
    text = '\n'.join(lines)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces → single space
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple blank lines → double newline
    
    # Fix common punctuation issues
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)  # Remove space before punctuation
    text = re.sub(r'([.,;:!?])([A-Za-z])', r'\1 \2', text)  # Add space after punctuation
    
    # Remove citation markers that sound bad when read aloud
    # e.g., "[1]", "(see Chapter 3)", "(ibid.)"
    text = re.sub(r'\[\d+\]', '', text)  # Remove [1], [23], etc.
    text = re.sub(r'\(see [^)]+\)', '', text)  # Remove "(see ...)"
    
    # Clean up quotes
    text = text.replace('"', '"').replace('"', '"')  # Smart quotes → straight quotes
    text = text.replace(''', "'").replace(''', "'")
    
    # Final cleanup
    text = text.strip()
    
    return text
