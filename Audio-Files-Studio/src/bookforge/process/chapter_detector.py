"""Multi-strategy chapter boundary detection for diverse text sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import re


@dataclass
class ChapterBoundary:
    """Detected chapter boundary with metadata."""
    line_index: int
    title: Optional[str]
    confidence: float  # 0.0 to 1.0
    strategy: str  # which detection method found this


class ChapterDetector:
    """Hierarchical chapter detection with multiple strategies."""

    # High-confidence structured patterns
    STRUCTURED_PATTERNS = [
        # "Chapter 1", "Chapter One", "CHAPTER I"
        (r'^CHAPTER\s+(?:[IVX]+|\d+|[A-Za-z]+)(?:\s*[:\-\.]?\s*.{0,50})?$', 0.95, 'chapter_number'),
        (r'^Chapter\s+(?:[IVX]+|\d+|[A-Za-z]+)(?:\s*[:\-\.]?\s*.{0,50})?$', 0.95, 'chapter_number'),
        
        # "1. Title" or "I. Title" (with optional title)
        (r'^(?:[IVX]+|\d+)\.\s+[A-Z][A-Za-z\s]+$', 0.85, 'numbered_section'),
        
        # Standalone numbers or roman numerals (common in fiction)
        (r'^\s*(?:[IVX]+|\d+)\s*$', 0.7, 'standalone_number'),
        
        # "Part One", "PART I"
        (r'^PART\s+(?:[IVX]+|[A-Za-z]+)(?:\s*[:\-\.]?\s*.{0,50})?$', 0.9, 'part_marker'),
        (r'^Part\s+(?:[IVX]+|[A-Za-z]+)(?:\s*[:\-\.]?\s*.{0,50})?$', 0.9, 'part_marker'),
        
        # Prologue, Epilogue, Introduction, etc.
        (r'^(?:PROLOGUE|EPILOGUE|PREFACE|INTRODUCTION|CONCLUSION|AFTERWORD)\s*$', 0.85, 'special_section'),
        (r'^(?:Prologue|Epilogue|Preface|Introduction|Conclusion|Afterword)\s*$', 0.85, 'special_section'),
        
        # All-caps titles (3-30 chars, avoid short headers)
        (r'^[A-Z][A-Z\s]{3,30}$', 0.6, 'caps_title'),
    ]

    # Words that boost chapter likelihood
    CHAPTER_KEYWORDS = [
        'chapter', 'part', 'section', 'book',
        'prologue', 'epilogue', 'introduction',
        'preface', 'afterword', 'interlude'
    ]

    def detect(
        self,
        text: str,
        strategy: str = "auto",
        min_confidence: float = 0.5
    ) -> List[ChapterBoundary]:
        """
        Detect chapter boundaries using specified strategy.

        Args:
            text: Full text to analyze
            strategy: Detection method - "auto", "markdown", "structured", 
                     "heuristic", "paragraph", "none"
            min_confidence: Minimum confidence threshold for boundaries

        Returns:
            List of detected chapter boundaries
        """
        if strategy == "none":
            return []

        if strategy == "auto":
            return self._detect_auto(text, min_confidence)
        elif strategy == "markdown":
            return self._detect_markdown(text)
        elif strategy == "structured":
            return self._detect_structured(text, min_confidence)
        elif strategy == "heuristic":
            return self._detect_heuristic(text, min_confidence)
        elif strategy == "paragraph":
            return self._detect_paragraph_breaks(text)
        else:
            raise ValueError(f"Unknown chapter detection strategy: {strategy}")

    def _detect_auto(self, text: str, min_confidence: float) -> List[ChapterBoundary]:
        """Try strategies in order of reliability until good results."""
        
        # Strategy 1: Markdown headers
        boundaries = self._detect_markdown(text)
        if boundaries and self._avg_confidence(boundaries) > 0.8:
            return boundaries

        # Strategy 2: Structured patterns (high confidence)
        boundaries = self._detect_structured(text, min_confidence=0.7)
        if boundaries and len(boundaries) >= 3:  # At least 3 chapters
            return boundaries

        # Strategy 3: Heuristic scoring (medium confidence)
        boundaries = self._detect_heuristic(text, min_confidence=0.5)
        if boundaries and len(boundaries) >= 3:
            return boundaries

        # Strategy 4: Fallback to paragraph breaks (current behavior)
        return self._detect_paragraph_breaks(text)

    def _detect_markdown(self, text: str) -> List[ChapterBoundary]:
        """Detect markdown-style headers (# Header, ## Subheader)."""
        lines = text.split('\n')
        boundaries = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            # Match # or ## at start (chapter-level headers)
            if re.match(r'^#{1,2}\s+.+$', line_stripped):
                level = len(re.match(r'^#+', line_stripped).group(0))
                title = line_stripped.lstrip('#').strip()
                
                boundaries.append(ChapterBoundary(
                    line_index=i,
                    title=title,
                    confidence=1.0 if level == 1 else 0.9,
                    strategy='markdown'
                ))

        return boundaries

    def _detect_structured(
        self,
        text: str,
        min_confidence: float = 0.7
    ) -> List[ChapterBoundary]:
        """Detect chapters using high-confidence regex patterns."""
        lines = text.split('\n')
        boundaries = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            for pattern, base_confidence, pattern_type in self.STRUCTURED_PATTERNS:
                match = re.match(pattern, line_stripped, re.IGNORECASE)
                if match:
                    confidence = base_confidence

                    # Boost confidence if surrounded by blank lines
                    if self._has_blank_context(lines, i):
                        confidence = min(1.0, confidence + 0.1)

                    # Boost if at start of text or after long gap
                    if i < 5 or self._after_long_gap(lines, i):
                        confidence = min(1.0, confidence + 0.05)

                    if confidence >= min_confidence:
                        boundaries.append(ChapterBoundary(
                            line_index=i,
                            title=line_stripped,
                            confidence=confidence,
                            strategy=f'structured:{pattern_type}'
                        ))
                    break  # Only match first pattern

        return self._filter_overlapping(boundaries)

    def _detect_heuristic(
        self,
        text: str,
        min_confidence: float = 0.5
    ) -> List[ChapterBoundary]:
        """Score potential chapter lines using contextual features."""
        lines = text.split('\n')
        scored = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty or very long lines
            if not line_stripped or len(line_stripped) > 100:
                continue

            score = 0.0

            # Feature 1: Starts with capital, short (5-50 chars)
            if line_stripped[0].isupper() and 5 <= len(line_stripped) <= 50:
                score += 0.2

            # Feature 2: Contains chapter-related keywords
            line_lower = line_stripped.lower()
            if any(keyword in line_lower for keyword in self.CHAPTER_KEYWORDS):
                score += 0.3

            # Feature 3: Surrounded by blank lines
            if self._has_blank_context(lines, i, window=2):
                score += 0.2

            # Feature 4: Followed by indented paragraph
            if i + 1 < len(lines) and lines[i + 1].startswith(('    ', '\t')):
                score += 0.1

            # Feature 5: Previous line was a page break indicator
            if i > 0 and lines[i - 1].strip() in ['***', '---', '* * *', '…']:
                score += 0.2

            # Feature 6: Line is centered (roughly)
            if self._is_centered(lines, i):
                score += 0.15

            # Feature 7: After long gap (page break simulation)
            if self._after_long_gap(lines, i, min_blank=3):
                score += 0.15

            if score >= min_confidence:
                scored.append(ChapterBoundary(
                    line_index=i,
                    title=line_stripped,
                    confidence=min(1.0, score),
                    strategy='heuristic'
                ))

        return self._filter_overlapping(scored)

    def _detect_paragraph_breaks(self, text: str) -> List[ChapterBoundary]:
        """Fallback: split on large gaps (current txt_ingest behavior)."""
        lines = text.split('\n')
        boundaries = []
        blank_run = 0

        for i, line in enumerate(lines):
            if not line.strip():
                blank_run += 1
            else:
                # Large gap detected
                if blank_run >= 5:
                    boundaries.append(ChapterBoundary(
                        line_index=i,
                        title=None,
                        confidence=0.4,
                        strategy='paragraph_break'
                    ))
                blank_run = 0

        return boundaries

    # --- Helper Methods ---

    def _has_blank_context(
        self,
        lines: List[str],
        index: int,
        window: int = 1
    ) -> bool:
        """Check if line is surrounded by blank lines."""
        before_blank = all(
            not lines[i].strip()
            for i in range(max(0, index - window), index)
            if i < len(lines)
        )
        after_blank = all(
            not lines[i].strip()
            for i in range(index + 1, min(len(lines), index + window + 1))
        )
        return before_blank and after_blank

    def _after_long_gap(
        self,
        lines: List[str],
        index: int,
        min_blank: int = 3
    ) -> bool:
        """Check if line comes after a run of blank lines."""
        if index < min_blank:
            return False

        return all(
            not lines[i].strip()
            for i in range(index - min_blank, index)
        )

    def _is_centered(self, lines: List[str], index: int) -> bool:
        """Rough heuristic: line has leading whitespace and is short."""
        line = lines[index]
        if not line or line[0] not in (' ', '\t'):
            return False

        stripped = line.strip()
        leading = len(line) - len(line.lstrip())
        # Centered if significant indent and short line
        return leading > 4 and len(stripped) < 60

    def _avg_confidence(self, boundaries: List[ChapterBoundary]) -> float:
        """Calculate average confidence of detected boundaries."""
        if not boundaries:
            return 0.0
        return sum(b.confidence for b in boundaries) / len(boundaries)

    def _filter_overlapping(
        self,
        boundaries: List[ChapterBoundary],
        min_distance: int = 10
    ) -> List[ChapterBoundary]:
        """Remove boundaries that are too close together."""
        if not boundaries:
            return []

        # Sort by line index
        sorted_boundaries = sorted(boundaries, key=lambda b: b.line_index)
        filtered = [sorted_boundaries[0]]

        for boundary in sorted_boundaries[1:]:
            if boundary.line_index - filtered[-1].line_index >= min_distance:
                filtered.append(boundary)

        return filtered
