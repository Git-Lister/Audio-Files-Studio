"""Abstract TTS backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..config import PresetConfig
from ..process.chunker import Chunk


class TTSBackend(ABC):
    """Base class for all TTS backends."""

    name: str = "base"

    @abstractmethod
    def load_model(self) -> None:
        """Load/initialize the model. Called before first synthesis."""

    @abstractmethod
    def synthesize_chunk(self, chunk: Chunk, config: PresetConfig, out_path: Path) -> None:
        """Synthesize a single chunk to out_path (WAV)."""

    def unload(self) -> None:
        """Release model resources. Optional no-op for most backends."""
