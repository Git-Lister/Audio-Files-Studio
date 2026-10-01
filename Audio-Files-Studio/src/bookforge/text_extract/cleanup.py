"""TTS-friendly text cleanup rules.

Each rule is a pure `str -> str` function. Rules are grouped into two tiers:
Tier 1 (cosmetic) and Tier 2 (structural). The pipeline applies rules in
definition order for a given enabled-rule set.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

from bookforge.process.chapter_detector import ChapterDetector


@dataclass
class CleanupRule:
    key: str
    label: str
    description: str
    func: Callable[[str], str]
    default_on: bool
    tier: int  # 1 or 2


# ---------- Tier 1 -- Cosmetic ----------

def _normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _strip_control_chars(text: str) -> str:
    return text.replace("\u200b", "").replace("\ufeff", "").replace("\r", "")


def _normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _fix_hyphenation(text: str) -> str:
    # word-\nword -> wordword (join words split across lines by layout)
    return re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)


def _normalize_dashes(text: str) -> str:
    return text.replace("\u2014", " - ").replace("\u2013", " - ")


def _normalize_quotes(text: str) -> str:
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    return text.replace("\u201c", '"').replace("\u201d", '"')


def _collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)


def _strip_trailing_ws(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.split("\n"))


def _remove_page_numbers(text: str) -> str:
    return re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)


def _expand_abbreviations(text: str) -> str:
    replacements = [
        ("e.g.", "for example"),
        ("E.g.", "For example"),
        ("i.e.", "that is"),
        ("I.e.", "That is"),
        ("etc.", "et cetera"),
        ("vs.", "versus"),
        ("c.f.", "compare"),
        ("et al.", "and others"),
        ("ibid.", "same source"),
        ("op. cit.", "previously cited"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


# ---------- Tier 2 -- Structural ----------

def _strip_footnote_markers(text: str) -> str:
    text = re.sub(r"\[\s*\d+(?:\s*[,-]\s*\d+)*\s*\]", "", text)
    text = re.sub(r"(?<=[a-zA-Z])(\d{1,4})(?=[\s.,;:!?]|$)", "", text)
    text = re.sub(r"(?<=[.,;:!?])(\d{1,4})(?=[\s.,;:!?]|$)", "", text)
    text = re.sub(r"(?<=[a-zA-Z.!?]) (\d{1,3})\.(?=\s|$)", ".", text)
    return text


def _reflow_paragraphs(text: str) -> str:
    """Join wrapped lines within each paragraph block into single lines.

    Appropriate for PDF and HTML extraction where every visual line is
    its own line in the extracted text. Not appropriate for already-formatted
    prose (txt, docx, epub) where paragraph breaks are meaningful.
    """
    blocks = text.split("\n\n")
    result: list[str] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if lines:
            result.append(" ".join(lines))
    return "\n\n".join(result)


def _detect_and_mark_chapters(text: str) -> str:
    detector = ChapterDetector()
    boundaries = detector.detect(text, strategy="auto")
    # Only mark if real chapters were found (paragraph-break fallback = no chapters).
    real = [
        b for b in boundaries
        if b.confidence >= 0.5 and b.strategy != "markdown"
    ]
    if not real:
        return text
    lines = text.split("\n")
    for b in real:
        if b.title and 0 <= b.line_index < len(lines):
            title = b.title.strip().replace("\n", " ")
            lines[b.line_index] = f"# {title}"
    return "\n".join(lines)


def _deduplicate_running_headers(text: str) -> str:
    """Remove short lines that repeat 3+ times across the document.

    Best-effort. Off by default because it can remove legitimate refrains
    or chapter titles that appear in a table of contents.
    """
    lines = text.split("\n")
    counts: dict[str, int] = {}
    for ln in lines:
        s = ln.strip()
        if 3 <= len(s) <= 60:
            counts[s] = counts.get(s, 0) + 1
    frequent = {s for s, n in counts.items() if n >= 3}
    if not frequent:
        return text
    return "\n".join(ln for ln in lines if ln.strip() not in frequent)


# ---------- Registry ----------

TIER1_RULES: list[CleanupRule] = [
    CleanupRule("normalize_unicode", "Normalise unicode",
                "Convert characters to a canonical form.", _normalize_unicode, True, 1),
    CleanupRule("strip_control_chars", "Strip control characters",
                "Remove zero-width and BOM characters.", _strip_control_chars, True, 1),
    CleanupRule("normalize_line_endings", "Normalise line endings",
                "Use LF consistently.", _normalize_line_endings, True, 1),
    CleanupRule("fix_hyphenation", "Fix hyphenation",
                "Rejoin words split across lines.", _fix_hyphenation, True, 1),
    CleanupRule("normalize_dashes", "Normalise dashes",
                "Replace em/en dashes with ' - '.", _normalize_dashes, True, 1),
    CleanupRule("normalize_quotes", "Normalise quotes",
                "Curly quotes to straight quotes.", _normalize_quotes, True, 1),
    CleanupRule("collapse_blank_lines", "Collapse blank lines",
                "Reduce 3+ blank lines to 2.", _collapse_blank_lines, True, 1),
    CleanupRule("strip_trailing_ws", "Strip trailing whitespace",
                "Remove trailing spaces per line.", _strip_trailing_ws, True, 1),
    CleanupRule("remove_page_numbers", "Remove page numbers",
                "Remove standalone numbers on their own lines.", _remove_page_numbers, True, 1),
    CleanupRule("expand_abbreviations", "Expand abbreviations",
                "'e.g.' becomes 'for example', etc.", _expand_abbreviations, True, 1),
]

TIER2_RULES: list[CleanupRule] = [
    CleanupRule("strip_footnote_markers", "Strip footnote markers",
                "Remove bracketed citations and superscripts.", _strip_footnote_markers, True, 2),
    CleanupRule("reflow_paragraphs", "Reflow paragraphs",
                "Join wrapped lines into single paragraphs. Recommended for PDF and HTML.",
                _reflow_paragraphs, False, 2),
    CleanupRule("detect_and_mark_chapters", "Detect and mark chapters",
                "Insert # headers at detected chapter boundaries.",
                _detect_and_mark_chapters, True, 2),
    CleanupRule("deduplicate_running_headers", "Remove running headers",
                "Remove lines that repeat 3+ times across the document. Risky.",
                _deduplicate_running_headers, False, 2),
]


def all_rules() -> list[CleanupRule]:
    return TIER1_RULES + TIER2_RULES


def default_enabled_keys() -> set[str]:
    return {r.key for r in all_rules() if r.default_on}


def clean(text: str, enabled_keys: set[str]) -> str:
    """Apply the selected cleanup rules in definition order."""
    for rule in all_rules():
        if rule.key in enabled_keys:
            text = rule.func(text)
    return text