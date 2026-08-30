"""Abstract TTS backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..process.chunker import Chunk
from ..config import PresetConfig


class TTSBackend(ABC):
    """Base class for all TTS backends."""

    @abstractmethod
    def synthesize_chunk(self, chunk: Chunk, config: PresetConfig, out_path: Path) -> None:
        """Synthesize a single chunk to out_path (WAV)."""
        raise NotImplementedError
