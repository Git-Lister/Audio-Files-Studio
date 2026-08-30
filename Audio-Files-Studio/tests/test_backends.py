from pathlib import Path

import pytest
import typer

from bookforge.cli import get_backend
from bookforge.tts.piper import PiperBackend
from bookforge.tts.xtts import XTTSBackend


def test_get_backend_piper_valid():
    model = Path("voices/test.onnx")
    backend = get_backend("piper", voice_model=model)
    assert isinstance(backend, PiperBackend)
    assert backend.model_path == str(model)

def test_get_backend_piper_missing_model():
    # Typer.BadParameter is raised if piper is used without a model
    with pytest.raises(typer.BadParameter, match="must provide --voice-model"):
        get_backend("piper", voice_model=None)

def test_get_backend_xtts():
    # XTTS should work even without a voice_model (uses speaker_wav or default)
    backend = get_backend("xtts", speaker_wav=Path("speaker.wav"))
    assert isinstance(backend, XTTSBackend)
    assert backend.speaker_wav == Path("speaker.wav")

def test_get_backend_invalid():
    with pytest.raises(typer.BadParameter, match="Unknown backend"):
        get_backend("invalid_backend")