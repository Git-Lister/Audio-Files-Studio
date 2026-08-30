"""Configuration and preset handling with XTTS parameter support."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, validator


class PresetConfig(BaseModel):
    """Voice and pacing configuration preset, extended with XTTS parameters."""

    voice: str
    rate: float = 1.0
    pitch: float = 0.0
    pause_short: float = 0.3
    pause_para: float = 1.2
    pause_chapter: float = 3.0
    seed: int = 42
    target_chunk_secs: int = 30

    # XTTS‑specific parameters (optional, only used if backend is XTTS)
    temperature: float | None = Field(default=0.667, ge=0.1, le=1.0)
    length_penalty: float | None = Field(default=1.0, ge=0.5, le=2.0)
    repetition_penalty: float | None = Field(default=5.0, ge=1.0, le=10.0)
    top_p: float | None = Field(default=0.8, ge=0.0, le=1.0)
    top_k: int | None = Field(default=50, ge=0)
    language: str | None = "en"
    retries: int = 3
    retry_delay: float = 1.0

    @validator("temperature")
    def valid_temperature(cls, v):
        if v is not None and not (0.1 <= v <= 1.0):
            raise ValueError("temperature must be between 0.1 and 1.0")
        return v

    @classmethod
    def load(cls, name: str) -> "PresetConfig":  # <-- string forward reference
        """Load preset from presets/<name>.yaml."""
        preset_file = Path(__file__).parent.parent.parent / "presets" / f"{name}.yaml"
        if not preset_file.exists():
            # Fallback to defaults with given name as voice
            return cls(voice=name)

        try:
            with preset_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return cls(**data)
        except Exception as e:
            raise ValueError(f"Failed to load preset '{name}': {e}") from e
