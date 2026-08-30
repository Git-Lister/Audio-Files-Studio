"""Chunking logic for BookForge."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from ..config import PresetConfig

WORDS_PER_MINUTE = 160.0  # conservative audiobook rate


@dataclass
class Chunk:
    id: int
    chapter_index: int
    relative_index: int  # within chapter
    text: str
    estimated_seconds: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "chapter_index": self.chapter_index,
            "relative_index": self.relative_index,
            "estimated_seconds": self.estimated_seconds,
            "file": f"chunk_{self.id:05d}.wav",
        }


def _estimate_seconds(text: str) -> float:
    words = len(text.split())
    if words == 0:
        return 0.0
    minutes = words / WORDS_PER_MINUTE
    return minutes * 60.0


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using punctuation boundaries."""
    # Split on .!? followed by space or newline, but keep delimiters
    sentences = re.split(r"(?<=[.!?])\s+", text)
    # Also handle cases where there's no space after punctuation (e.g., "Hello.World")
    # We'll just split on .!? and add a space
    # For simplicity, we'll use the regex.
    # Also handle double newline as paragraph break.
    return [s.strip() for s in sentences if s.strip()]


def chunk_chapter(
    chapter_text: str,
    config: PresetConfig,
    chapter_index: int,
    starting_chunk_id: int = 0,
) -> List[Chunk]:
    """Split a chapter into approximate-length chunks, respecting sentence boundaries."""
    # First, split into paragraphs (double newline)
    paragraphs = [p.strip() for p in chapter_text.split("\n\n") if p.strip()]
    # Flatten paragraphs into sentences, but keep paragraph boundaries as cues.
    # We'll treat each paragraph as a group, but we can still split sentences within.
    # We'll build chunks by accumulating sentences until target duration.
    target = float(config.target_chunk_secs)
    min_chunk_duration = 5.0  # seconds

    chunks: List[Chunk] = []
    current_chunk_id = starting_chunk_id
    rel_idx = 0

    current_sentences: List[str] = []

    def flush():
        nonlocal current_sentences, current_chunk_id, rel_idx
        if not current_sentences:
            return
        text = " ".join(current_sentences)
        est = _estimate_seconds(text)
        # If est < min_chunk_duration and we have previous chunks, consider merging with previous
        # but for simplicity, we'll still create a chunk.
        chunks.append(
            Chunk(
                id=current_chunk_id,
                chapter_index=chapter_index,
                relative_index=rel_idx,
                text=text,
                estimated_seconds=est,
            )
        )
        current_chunk_id += 1
        rel_idx += 1
        current_sentences = []

    for para in paragraphs:
        sentences = _split_into_sentences(para)
        # Add a sentence-level pause marker: we can insert a comma or extra space, but we'll just add the sentence.
        for sent in sentences:
            # Check if adding this sentence exceeds target
            candidate_text = " ".join(current_sentences + [sent])
            if _estimate_seconds(candidate_text) > target and current_sentences:
                flush()
            current_sentences.append(sent)
        # After paragraph, add a paragraph break cue: we can add a short pause by inserting a comma or multiple spaces.
        # We'll not insert anything now, but we could add a special token.
    flush()

    # Merge very small chunks with previous if possible (optional)
    # For now, return as is.
    return chunks
