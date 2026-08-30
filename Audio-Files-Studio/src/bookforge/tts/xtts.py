"""XTTS v2 TTS backend with automatic long-chunk splitting, retry, and parameter control."""

from __future__ import annotations

import logging
import re
import time
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

from TTS.api import TTS

from ..audio.concat import concat_wavs
from ..config import PresetConfig
from ..process.chunker import Chunk
from ..process.sanitize import sanitise_for_tts
from .backend import TTSBackend

logger = logging.getLogger("bookforge.tts.xtts")


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
                    # Force split at word boundaries
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
    """XTTS v2 backend with full parameter control and retry logic."""

    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        gpu: bool | None = None,  # None = auto‑detect
        speaker_wav: Path | None = None,
        language: str = "en",
        temperature: float = 0.667,
        length_penalty: float = 1.0,
        repetition_penalty: float = 5.0,
        top_p: float = 0.8,
        top_k: int = 50,
        retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        if gpu is None:
            gpu = torch.cuda.is_available()
        device = "cuda" if gpu and torch.cuda.is_available() else "cpu"
        self._device = device
        self._model_name = model_name
        self._speaker_wav = str(speaker_wav) if speaker_wav else None
        self._language = language
        self._temperature = temperature
        self._length_penalty = length_penalty
        self._repetition_penalty = repetition_penalty
        self._top_p = top_p
        self._top_k = top_k
        self._retries = retries
        self._retry_delay = retry_delay

        logger.info(f"Loading XTTS model '{model_name}' on {device}...")
        self.tts = TTS(model_name).to(device)
        logger.info("XTTS model loaded.")

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
            self._synthesise_with_retry(safe_text, out_path)
            return

        segments = _split_safe(safe_text, max_chars=250)
        if len(segments) == 1:
            self._synthesise_with_retry(segments[0], out_path)
            return

        temp_files: list[Path] = []
        try:
            for i, seg in enumerate(segments):
                tmp = out_path.with_name(f"{out_path.stem}_part_{i:04d}.wav")
                temp_files.append(tmp)
                self._synthesise_with_retry(seg, tmp)
            concat_wavs(temp_files, out_path)
        except Exception as e:
            # If concatenation fails, clean up partials and re‑raise
            for tmp in temp_files:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
            raise RuntimeError(f"Failed to concatenate segments for chunk {chunk.id}: {e}") from e
        finally:
            # Delete temporary files after success
            for tmp in temp_files:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass

    def _synthesise_with_retry(self, text: str, file_path: Path) -> None:
        """Synthesise a single text segment with exponential backoff retry."""
        for attempt in range(1, self._retries + 1):
            try:
                self._synthesise_directly(text, file_path)
                return
            except Exception as e:
                logger.warning(f"Synthesis attempt {attempt}/{self._retries} failed: {e}")
                if attempt == self._retries:
                    raise RuntimeError(
                        f"All {self._retries} attempts failed for text: {text[:50]}..."
                    ) from e
                time.sleep(self._retry_delay * (2 ** (attempt - 1)))

    def _synthesise_directly(self, text: str, file_path: Path) -> None:
        """Low‑level synthesis call with all parameters."""
        kwargs = {
            "text": text,
            "file_path": str(file_path),
            "temperature": self._temperature,
            "length_penalty": self._length_penalty,
            "repetition_penalty": self._repetition_penalty,
            "top_p": self._top_p,
            "top_k": self._top_k,
        }
        if self._speaker_wav:
            kwargs["speaker_wav"] = self._speaker_wav
        if self._language:
            kwargs["language"] = self._language

        logger.debug(f"Synthesising: {text[:60]}...")
        self.tts.tts_to_file(**kwargs)
        logger.debug(f"Saved to {file_path}")
