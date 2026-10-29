"""Voice profile: decouple voice definition from the TTS engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class VoiceProfile:
    backend_type: str = "xtts"          # "xtts" | "f5" (styletts2 future)
    reference_wav: Path | None = None   # For XTTS / zero-shot cloning
    accent: str | None = None           # e.g. "Irish"

    language: str = "en"
    temperature: float = 0.667
    length_penalty: float = 1.0
    repetition_penalty: float = 5.0
    top_p: float = 0.8
    top_k: int = 50
    pitch: float = 0.0
    rate: float = 1.0
    num_beams: int = 3
    preset_name: str = "calm_longform"

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.reference_wav:
            d["reference_wav"] = str(self.reference_wav)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "VoiceProfile":
        known = {f for f in cls.__dataclass_fields__}
        cleaned = {k: v for k, v in d.items() if k in known}

        # Handle legacy keys from older projects/DB rows
        if "speaker_wav" in d and not cleaned.get("reference_wav"):
            cleaned["reference_wav"] = d["speaker_wav"]
        elif "reference_wav_path" in d and not cleaned.get("reference_wav"):
            cleaned["reference_wav"] = d["reference_wav_path"]
        if cleaned.get("reference_wav"):
            cleaned["reference_wav"] = Path(cleaned["reference_wav"])

        return cls(**cleaned)
