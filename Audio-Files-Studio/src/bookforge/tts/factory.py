"""TTS backend factory driven by a VoiceProfile."""

from __future__ import annotations

from typing import Any

from ..voice_profile import VoiceProfile
from .backend import TTSBackend


def get_backend(voice: VoiceProfile, **overrides: Any) -> TTSBackend:
    """Instantiate the correct TTS backend from a VoiceProfile."""
    backend_type = voice.backend_type.lower().strip()

    if backend_type == "xtts":
        if voice.reference_wav is None:
            raise ValueError("reference_wav is required for XTTS backend.")
        if not voice.reference_wav.exists():
            raise FileNotFoundError(f"Speaker WAV not found: {voice.reference_wav}")

        try:
            from .xtts import XTTSBackend
        except ModuleNotFoundError as e:
            raise ImportError(
                "XTTS dependencies are not installed. Please install torch and Coqui TTS."
            ) from e

        params = {
            "speaker_wav": voice.reference_wav,
            "language": voice.language,
            "temperature": voice.temperature,
            "length_penalty": voice.length_penalty,
            "repetition_penalty": voice.repetition_penalty,
            "top_p": voice.top_p,
            "top_k": voice.top_k,
            "pitch": voice.pitch,
            "rate": voice.rate,
            "num_beams": voice.num_beams,
        }
        params.update(overrides)
        return XTTSBackend(**params)

    if backend_type == "f5":
        from .f5 import F5Backend

        return F5Backend(
            speaker_wav=voice.reference_wav,
            language=voice.language,
            speed=voice.rate,
        )

    raise ValueError(f"Unknown backend: {backend_type}")
