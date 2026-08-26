"""XTTS v2 TTS backend with automatic long-chunk splitting."""

from __future__ import annotations

import re
from pathlib import Path

import torch

# ---------------------------------------------------------------------------
# PyTorch 2.6+ compatibility: Coqui TTS checkpoints need weights_only=False
# ---------------------------------------------------------------------------
_original_torch_load = torch.load


def _torch_load_allow_weights(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _original_torch_load(*args, **kwargs)


torch.load = _torch_load_allow_weights
# ---------------------------------------------------------------------------

from TTS.api import TTS  # coqui-tts

from ..audio.concat import concat_wavs
from ..config import PresetConfig
from ..process.chunker import Chunk
from ..process.sanitize import sanitise_for_tts
from .backend import TTSBackend


def _split_safe(text: str, max_chars: int = 250) -> list[str]:
    """Split text into segments ≤ max_chars, trying to break at sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    segments = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(s) <= max_chars:
            segments.append(s)
        else:
            sub_parts = re.split(r"(?<=[,;:])\s+", s)
            for part in sub_parts:
                if len(part) <= max_chars:
                    segments.append(part)
                else:
                    words = part.split()
                    current = ""
                    for w in words:
                        if len(current) + len(w) + 1 <= max_chars:
                            current = (current + " " + w) if current else w
                        else:
                            if current:
                                segments.append(current)
                            current = w
                    if current:
                        segments.append(current)
    return segments


class XTTSBackend(TTSBackend):
    """XTTS v2 backend using Coqui TTS."""

    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        gpu: bool = True,
        speaker_wav: Path | None = None,
        language: str = "en",
    ) -> None:
        device = "cuda" if gpu and torch.cuda.is_available() else "cpu"
        self._device = device
        self._model_name = model_name
        self._speaker_wav = str(speaker_wav) if speaker_wav else None
        self._language = language
        self.tts = TTS(model_name).to(device)

    @property
    def device(self) -> str:
        return self._device

    def synthesize_chunk(
        self,
        chunk: Chunk,
        config: PresetConfig,
        out_path: Path,
    ) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        safe_text = sanitise_for_tts(chunk.text)

        if len(safe_text) <= 250:
            self._synthesise_directly(safe_text, out_path)
            return

        segments = _split_safe(safe_text, max_chars=250)
        if len(segments) == 1:
            self._synthesise_directly(segments[0], out_path)
            return

        temp_files: list[Path] = []
        try:
            for i, seg in enumerate(segments):
                tmp = out_path.with_name(f"{out_path.stem}_part_{i:04d}.wav")
                temp_files.append(tmp)
                self._synthesise_directly(seg, tmp)
            concat_wavs(temp_files, out_path)
        finally:
            for tmp in temp_files:
                try:
                    tmp.unlink()
                except OSError:
                    pass

    def _synthesise_directly(self, text: str, file_path: Path) -> None:
        kwargs = {
            "text": text,
            "file_path": str(file_path),
        }
        if self._speaker_wav:
            kwargs["speaker_wav"] = self._speaker_wav
        if self._language:
            kwargs["language"] = self._language
        self.tts.tts_to_file(**kwargs)
