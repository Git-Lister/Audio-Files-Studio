"""StyleTTS2 Backend – human-level prosody and accent retention."""

from __future__ import annotations
import logging
from pathlib import Path

from ..process.chunker import Chunk
from ..config import PresetConfig
from .backend import TTSBackend
from .exceptions import CudaDeviceAssertError

logger = logging.getLogger("bookforge.tts.styletts2")


class StyleTTS2Backend(TTSBackend):
    name = "styletts2"

    def __init__(self, speaker_wav: Path | None = None, language: str = "en", speed: float = 1.0, **kwargs):
        self._speaker_wav = str(speaker_wav) if speaker_wav else None
        self._language = language
        self._speed = speed
        self._model = None

    def load_model(self) -> None:
        if self._model is not None:
            return

        logger.warning("Loading StyleTTS2 model via PyPI package...")
        try:
            from styletts2.tts import StyleTTS2
            self._model = StyleTTS2(
                model_checkpoint_path=None,
                config_path=None,
                phoneme_converter="gruut",
            )
        except ImportError as e:
            raise ImportError("StyleTTS2 is not installed. Please rebuild the container.") from e

    def synthesize_chunk(self, chunk: Chunk, config: PresetConfig, out_path: Path) -> None:
        if self._model is None:
            self.load_model()
        if not self._speaker_wav:
            raise ValueError("StyleTTS2 requires a reference WAV.")

        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            logger.debug(f"StyleTTS2 Synthesising: {chunk.text[:50]}...")
            # StyleTTS2.PyPI API: StyleTTS2.inference(text, target_voice_path, output_wav_file, ...)
            self._model.inference(
                text=chunk.text,
                target_voice_path=self._speaker_wav,
                output_wav_file=str(out_path),
            )
        except Exception as e:
            err_str = str(e)
            if "device-side assert" in err_str or "CUDA error" in err_str:
                raise CudaDeviceAssertError(f"StyleTTS2 GPU context corrupted: {err_str}") from e
            raise RuntimeError(f"StyleTTS2 synthesis failed: {e}") from e

    def unload(self) -> None:
        self._model = None
        import torch
        torch.cuda.empty_cache()
