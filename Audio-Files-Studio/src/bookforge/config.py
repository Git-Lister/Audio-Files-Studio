# src/bookforge/config.py
"""Configuration and preset handling with full JSON support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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

    # XTTS‑specific parameters
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
    def load(cls, name: str) -> PresetConfig:
        """Load a preset: first check system presets, then user presets."""
        # System presets (read-only)
        system_path = Path(__file__).parent.parent.parent / "presets" / f"{name}.json"
        if system_path.exists():
            with system_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)

        # User presets (read/write)
        user_path = Path(__file__).parent.parent.parent / "presets" / "user" / f"{name}.json"
        if user_path.exists():
            with user_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)

        # Fallback to defaults with given name as voice
        return cls(voice=name)

    @classmethod
    def list_presets(cls) -> dict[str, list[str]]:
        """Return {'system': [...], 'user': [...]} with preset names."""
        base_dir = Path(__file__).parent.parent.parent / "presets"
        user_dir = base_dir / "user"

        system_presets = []
        if base_dir.exists():
            system_presets = [f.stem for f in base_dir.glob("*.json") if f.is_file()]

        user_presets = []
        if user_dir.exists():
            user_presets = [f.stem for f in user_dir.glob("*.json") if f.is_file()]

        return {"system": sorted(system_presets), "user": sorted(user_presets)}

    @classmethod
    def save_user_preset(cls, name: str, data: dict[str, Any]) -> None:
        """Save a user preset to presets/user/{name}.json."""
        user_dir = Path(__file__).parent.parent.parent / "presets" / "user"
        user_dir.mkdir(parents=True, exist_ok=True)

        # Validate the data against the model
        validated = cls(**data)
        user_path = user_dir / f"{name}.json"
        with user_path.open("w", encoding="utf-8") as f:
            json.dump(validated.dict(), f, indent=2)

    @classmethod
    def delete_user_preset(cls, name: str) -> bool:
        """Delete a user preset. Returns True if deleted, False if not found."""
        user_path = Path(__file__).parent.parent.parent / "presets" / "user" / f"{name}.json"
        if user_path.exists():
            user_path.unlink()
            return True
        return False
