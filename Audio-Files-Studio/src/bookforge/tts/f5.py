"""F5-TTS Backend – fast, non-autoregressive zero-shot cloning."""

from __future__ import annotations

import logging
import os
import ssl
from pathlib import Path

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..config import PresetConfig
from ..process.chunker import Chunk
from .backend import TTSBackend
from .exceptions import CudaDeviceAssertError

# =====================================================================
# BULLETPROOF SSL BYPASS (For Kaspersky / Corporate Firewalls)
# This forces Python, HuggingFace, and Whisper to ignore SSL errors.
# =====================================================================
# 1. Bypass SSL for standard urllib
if hasattr(ssl, "_create_unverified_context"):
    ssl._create_default_https_context = ssl._create_unverified_context

# 2. Bypass SSL for HuggingFace / Transformers env vars
os.environ["HF_HUB_DISABLE_SSL_VERIFY"] = "1"
os.environ["PYTHONHTTPSVERIFY"] = "0"

# 3. Monkeypatch requests to globally disable SSL verification
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
_original_session_init = requests.Session.__init__


def _patched_session_init(self, *args, **kwargs):
    _original_session_init(self, *args, **kwargs)
    self.verify = False


requests.Session.__init__ = _patched_session_init
# =====================================================================

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
        except Exception as e:
            # Do not mask the real error (e.g. missing pyarrow, bad numpy version)
            raise RuntimeError(f"Failed to load F5-TTS due to a dependency error: {e}") from e

        logger.info("Loading F5-TTS model...")
        logger.warning("Loading F5-TTS model. First run may download ~1.5GB from HuggingFace.")
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
                ref_text="",  # F5 will auto-transcribe using Whisper
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
