"""TTS backend factory with parameter forwarding."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def get_backend(
    backend_type: str,
    voice_model: Path | None = None,
    speaker_wav: Path | None = None,
    **kwargs: Any,
):
    """Instantiate the correct TTS backend, passing additional kwargs."""
    backend_type = backend_type.lower().strip()

    if backend_type == "piper":
        if voice_model is None:
            raise ValueError("--voice-model is required for Piper backend.")
        from .piper import PiperBackend

        return PiperBackend(str(voice_model))

    if backend_type == "xtts":
        if speaker_wav is None:
            raise ValueError("speaker_wav is required for XTTS backend.")
        if not speaker_wav.exists():
            raise FileNotFoundError(f"Speaker WAV not found: {speaker_wav}")
        try:
            from .xtts import XTTSBackend
        except ModuleNotFoundError as e:
            raise ImportError(
                "XTTS dependencies are not installed. Please install torch and Coqui TTS."
            ) from e

        # Extract only the parameters that XTTSBackend accepts
        xtts_params = {
            k: v
            for k, v in kwargs.items()
            if k
            in [
                "model_name",
                "gpu",
                "language",
                "temperature",
                "length_penalty",
                "repetition_penalty",
                "top_p",
                "top_k",
                "retries",
                "retry_delay",
            ]
        }
        return XTTSBackend(speaker_wav=speaker_wav, **xtts_params)

    raise ValueError(f"Unknown backend: {backend_type}")
