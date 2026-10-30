"""F5-TTS Backend – fast, non-autoregressive zero-shot cloning."""

from __future__ import annotations

import logging
from pathlib import Path

from ..config import PresetConfig
from ..process.chunker import Chunk
from .backend import TTSBackend
from .exceptions import CudaDeviceAssertError

logger = logging.getLogger("bookforge.tts.f5")


class F5Backend(TTSBackend):
    name = "f5"

    def __init__(
        self,
        speaker_wav: Path | None = None,
        language: str = "en",
        speed: float = 1.0,
    ):
        self._speaker_wav = str(speaker_wav) if speaker_wav else None
        self._language = language
        self._speed = speed
        self._model = None

    def load_model(self) -> None:
        if self._model is not None:
            return
        try:
            from f5_tts.api import F5TTS
        except ImportError as e:
            raise ImportError("f5-tts is not installed. Please rebuild the container.") from e

        logger.info("Loading F5-TTS model...")
        # 'F5TTS_v1_Base' is the standard pre-trained model.
        self._model = F5TTS(model="F5TTS_v1_Base", device="cuda")
        logger.info("F5-TTS loaded.")

    def synthesize_chunk(self, chunk: Chunk, config: PresetConfig, out_path: Path) -> None:
        if self._model is None:
            self.load_model()
        if not self._speaker_wav:
            raise ValueError("F5-TTS requires a reference WAV for zero-shot cloning.")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        text = chunk.text

        try:
            logger.debug(f"F5 Synthesising: {text[:50]}...")
            self._model.infer(
                ref_file=self._speaker_wav,
                ref_text="",  # F5 can auto-transcribe, or we can provide it
                gen_text=text,
                file_wave=str(out_path),
                speed=self._speed,
                remove_silence=False,  # We handle silence in post-processing
            )
        except Exception as e:
            err_str = str(e)
            if "device-side assert" in err_str or "CUDA error" in err_str:
                raise CudaDeviceAssertError(f"F5-TTS GPU context corrupted: {err_str}") from e
            raise RuntimeError(f"F5 synthesis failed: {e}") from e

    def unload(self) -> None:
        self._model = None
        import torch

        torch.cuda.empty_cache()
