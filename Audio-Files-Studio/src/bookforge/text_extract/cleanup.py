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


def _collapse_internal_whitespace(text: str) -> str:
    """Collapse runs of 2+ spaces to a single space within each line."""
    return "\n".join(re.sub(r" {2,}", " ", ln) for ln in text.split("\n"))


def _strip_urls(text: str) -> str:
    """Remove URLs and DOIs, including spaced-out forms from PDF extraction."""
    # Spaced-out URLs: "h t t p s : / /" — collapse them first so the main pattern can match
    text = re.sub(r"h\s+t\s+t\s+p\s+s?\s*:\s*/\s*/\s*", "https://", text, flags=re.IGNORECASE)
    # Standard URLs
    text = re.sub(r"https?://\S+", "", text)
    # DOI identifiers, both "10.xxxx/yyyy" and spaced variants
    text = re.sub(r"\b1\s*0\s*\.\s*\d{4,5}\s*/\s*\S+", "", text)
    # Dangling "doi.org" prefix from a URL whose scheme was removed
    text = re.sub(r"\bdoi\.org\S*", "", text)
    # Spaced-out domain fragments (e.g. "o i . o r g", "c o m m o n s . o r g")
    text = re.sub(
        r"\b(?:[a-zA-Z]\s+){2,}[a-zA-Z]\.[a-zA-Z]{2,}(?:/[^\s]*)?",
        "",
        text,
    )
    return text


def _strip_emails(text: str) -> str:
    """Remove email addresses."""
    return re.sub(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", "", text)


def _remove_page_numbers(text: str) -> str:
    # Standalone number
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    # Two short number groups on their own line, e.g. Springer's "1 3"
    text = re.sub(r"^\s*\d{1,2}\s+\d{1,2}\s*$", "", text, flags=re.MULTILINE)
    # Running header concatenated with page number (e.g. "RESEARCH380")
    text = re.sub(r"\b[A-Z]{3,}\d{1,4}\b", "", text)
    return text


def _expand_abbreviations(text: str) -> str:
    replacements = [
        ("e.g.", "for example"),
        ("E.g.", "For example"),
        ("i.e.", "that is"),
        ("I.e.", "That is"),
        ("etc.", "et cetera"),
        ("vs.", "versus"),
        ("c.f.", "compare"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


# ---------- Tier 2 -- Structural ----------

def _strip_footnote_markers(text: str) -> str:
    # Bracketed numeric citations (kept from original)
    text = re.sub(r"\[\s*\d+(?:\s*[,-]\s*\d+)*\s*\]", "", text)
    # Lowercase letter immediately followed by 1-2 digits, then whitespace/punct
    # (avoids uppercase-prefixed tokens like R1049, B12, H2O)
    text = re.sub(r"(?<=[a-z])(\d{1,2})(?=[\s.,;:!?]|$)", "", text)
    # Digits following sentence punctuation
    text = re.sub(r"(?<=[.,;:!?])(\d{1,4})(?=[\s.,;:!?]|$)", "", text)
    # "word. 1." style trailing footnote numbers
    text = re.sub(r"(?<=[a-zA-Z.!?]) (\d{1,3})\.(?=\s|$)", ".", text)
    return text


def _strip_journal_metadata(text: str) -> str:
    """Remove the standard journal submission metadata block from academic PDFs."""
    # Recognise the pattern: one or more "Received/Revised/Accepted/Published online" lines
    pattern = (
        r"^\s*(?:Received|Revised|Accepted|Published online|Published|"
        r"©\s*The Author|This article is licensed)\b.*$"
    )
    return re.sub(pattern, "", text, flags=re.MULTILINE | re.IGNORECASE)


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


def _mark_numbered_sections(text: str) -> str:
    """Mark academic-style numbered section headers ('1 Introduction') as '# '."""
    return re.sub(
        r"^(\d{1,2})\s+([A-Z][A-Za-z,&\s\-']{3,60})$",
        r"# \1 \2",
        text,
        flags=re.MULTILINE,
    )


def _strip_references_section(text: str) -> str:
    """Truncate text at a References / Bibliography / Works Cited heading.

    Off by default. When enabled, everything from the heading line to the
    end of the document is removed. If no such heading is found, text is
    unchanged.
    """
    pattern = r"^\s*#?\s*(?:References|Bibliography|Works\s+Cited|Further\s+Reading)\s*$"
    match = re.search(pattern, text, flags=re.MULTILINE | re.IGNORECASE)
    if match is None:
        return text
    return text[: match.start()].rstrip()


def _deduplicate_running_headers(text: str) -> str:
    """Remove short lines that repeat 5+ times across the document.

    Tightened from the earlier version: requires 5+ occurrences (not 3) so
    legit refrains survive. Length range extended to 4-80 chars to catch
    journal headers like 'Philosophia (2026) 54: - 396'. On by default now
    that false positives are rare.
    """
    lines = text.split("\n")
    counts: dict[str, int] = {}
    for ln in lines:
        s = ln.strip()
        if 4 <= len(s) <= 80:
            counts[s] = counts.get(s, 0) + 1
    frequent = {s for s, n in counts.items() if n >= 5}
    if not frequent:
        return text
    return "\n".join(ln for ln in lines if ln.strip() not in frequent)


# ---------- Registry ----------

ALL_RULES: list[CleanupRule] = [
    # Tier 1 (cosmetic)
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
    CleanupRule("collapse_internal_whitespace", "Collapse internal whitespace",
                "Replace runs of multiple spaces with a single space.",
                _collapse_internal_whitespace, True, 1),
    CleanupRule("strip_urls", "Remove URLs and DOIs",
                "Strip web addresses and DOI identifiers that would be read character-by-character.",
                _strip_urls, True, 1),
    CleanupRule("strip_emails", "Remove email addresses",
                "Strip email addresses that would be read character-by-character.",
                _strip_emails, True, 1),
    CleanupRule("remove_page_numbers", "Remove page numbers",
                "Remove standalone numbers on their own lines.", _remove_page_numbers, True, 1),
    CleanupRule("expand_abbreviations", "Expand common abbreviations",
                "'e.g.' \u2192 'for example', 'etc.' \u2192 'et cetera'. "
                "Academic Latin abbreviations (et al., ibid., op. cit.) are preserved.",
                _expand_abbreviations, True, 1),
    CleanupRule("strip_footnote_markers", "Strip footnote markers",
                "Remove bracketed citations and superscript numbers. "
                "Off by default: can mis-fire on tokens like 'R1049' or 'B12'.",
                _strip_footnote_markers, False, 1),
    # Tier 2 (structural)
    CleanupRule("strip_journal_metadata", "Remove journal metadata",
                "Strip academic paper submission metadata (Received/Revised/Accepted/Published online). "
                "Only fires on academic PDFs.",
                _strip_journal_metadata, True, 2),
    CleanupRule("reflow_paragraphs", "Reflow paragraphs",
                "Join wrapped lines into single paragraphs. Recommended for PDF and HTML.",
                _reflow_paragraphs, False, 2),
    CleanupRule("strip_references_section", "Remove References section",
                "Truncate the document at a References / Bibliography heading. "
                "Off by default: preserves references for those who want them.",
                _strip_references_section, False, 2),
    CleanupRule("detect_and_mark_chapters", "Detect and mark chapters",
                "Insert # headers at detected chapter boundaries.",
                _detect_and_mark_chapters, True, 2),
    CleanupRule("deduplicate_running_headers", "Remove repeated short lines",
                "Remove lines that repeat 5+ times across the document (running headers). "
                "Turn off for scripts or poetry with intentional refrains.",
                _deduplicate_running_headers, True, 2),
    CleanupRule("mark_numbered_sections", "Mark numbered sections",
                "Prefix academic section headers ('1 Introduction') with '# ' so the pipeline "
                "detects them as chapter boundaries. Off by default: can false-positive on "
                "documents that use numbered list items.",
                _mark_numbered_sections, False, 2),
]

_RULES_BY_KEY: dict[str, CleanupRule] = {r.key: r for r in ALL_RULES}


PHASES: list[tuple[str, list[str]]] = [
    ("normalise", [
        "normalize_unicode",
        "normalize_line_endings",
        "strip_control_chars",
        "strip_trailing_ws",
        "normalize_dashes",
        "normalize_quotes",
    ]),
    ("strip_lines", [
        "remove_page_numbers",
        "deduplicate_running_headers",
        "strip_journal_metadata",
    ]),
    ("strip_inline", [
        "strip_urls",
        "strip_emails",
        "strip_footnote_markers",
    ]),
    ("reflow", [
        "fix_hyphenation",
        "collapse_internal_whitespace",
        "collapse_blank_lines",
        "reflow_paragraphs",
    ]),
    ("expand", [
        "expand_abbreviations",
    ]),
    ("structure", [
        "strip_references_section",
        "detect_and_mark_chapters",
        "mark_numbered_sections",
    ]),
]


def _validate_phases() -> None:
    """Assert every rule appears exactly once in PHASES; no unknown keys."""
    seen: list[str] = []
    for _phase_name, rule_keys in PHASES:
        for key in rule_keys:
            if key in seen:
                raise RuntimeError(f"Rule '{key}' appears in multiple phases")
            seen.append(key)
    all_keys = {r.key for r in ALL_RULES}
    missing = all_keys - set(seen)
    extra = set(seen) - all_keys
    if missing:
        raise RuntimeError(f"Rules not assigned to any phase: {missing}")
    if extra:
        raise RuntimeError(f"Unknown rules listed in PHASES: {extra}")


_validate_phases()


def all_rules() -> list[CleanupRule]:
    return list(ALL_RULES)


def default_enabled_keys() -> set[str]:
    return {r.key for r in ALL_RULES if r.default_on}


def clean(text: str, enabled_keys: set[str]) -> str:
    """Apply the pipeline, running enabled rules in phase order."""
    for _phase_name, rule_keys in PHASES:
        for key in rule_keys:
            if key in enabled_keys:
                text = _RULES_BY_KEY[key].func(text)
    return text


def clean_debug(text: str, enabled_keys: set[str]) -> list[dict]:
    """Like clean(), but returns a per-rule trace instead of the text.

    Each entry: {phase, rule_key, chars_before, chars_after, delta}.
    """
    trace: list[dict] = []
    for phase_name, rule_keys in PHASES:
        for key in rule_keys:
            if key in enabled_keys:
                rule = _RULES_BY_KEY[key]
                before = len(text)
                text = rule.func(text)
                after = len(text)
                trace.append({
                    "phase": phase_name,
                    "rule_key": key,
                    "chars_before": before,
                    "chars_after": after,
                    "delta": after - before,
                })
    return trace