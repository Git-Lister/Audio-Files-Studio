"""Chunking logic for BookForge."""

from __future__ import annotations

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
        """Serialize chunk metadata (excluding text) for project index."""
        return {
            "id": self.id,
            "chapter_index": self.chapter_index,
            "relative_index": self.relative_index,
            "estimated_seconds": self.estimated_seconds,
            # Audio file name is derived from id
            "file": f"chunk_{self.id:05d}.wav",
        }


def _estimate_seconds(text: str) -> float:
    words = len(text.split())
    if words == 0:
        return 0.0
    minutes = words / WORDS_PER_MINUTE
    return minutes * 60.0


def chunk_chapter(
    chapter_text: str,
    config: PresetConfig,
    chapter_index: int,
    starting_chunk_id: int = 0,
) -> List[Chunk]:
    """Split a chapter into approximate-length chunks.

    Heuristic:
    - Split by paragraph (double newline).
    - Append paragraphs until estimated duration would exceed target_chunk_secs.
    - Then start a new chunk.
    """
    paragraphs = [p.strip() for p in chapter_text.split("\n\n") if p.strip()]
    chunks: List[Chunk] = []
    current_paras: List[str] = []
    current_chunk_id = starting_chunk_id
    rel_idx = 0

    target = float(config.target_chunk_secs)

    def flush() -> None:
        nonlocal current_paras, current_chunk_id, rel_idx
        if not current_paras:
            return
        text = "\n\n".join(current_paras)
        est = _estimate_seconds(text)
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
        current_paras = []

    for para in paragraphs:
        candidate = "\n\n".join(current_paras + [para]) if current_paras else para
        if _estimate_seconds(candidate) > target and current_paras:
            flush()
            current_paras.append(para)
        else:
            current_paras.append(para)

    flush()
    return chunks
