"""Mock test to verify TTS factory routing without loading models.

XTTSBackend loads the model eagerly in __init__, and importing it pulls in
torch + Coqui TTS, so we do not instantiate it here. Instead we verify the
factory's XTTS branch by its distinctive reference-WAV validation error.
"""

from pathlib import Path

from bookforge.tts.f5 import F5Backend
from bookforge.tts.factory import get_backend
from bookforge.voice_profile import VoiceProfile


def test_factory_routes_to_f5():
    profile = VoiceProfile(
        backend_type="f5",
        reference_wav=Path("dummy.wav"),
        language="en",
    )
    # F5Backend.__init__ is lazy (no model load), so this is safe to instantiate.
    backend = get_backend(profile)
    assert isinstance(backend, F5Backend)
    assert backend.name == "f5"
    print("✅ Factory correctly routes to F5Backend")


def test_factory_routes_to_xtts():
    profile = VoiceProfile(
        backend_type="xtts",
        reference_wav=Path("dummy.wav"),
        language="en",
    )
    # The XTTS branch validates that the reference WAV exists before it tries
    # to instantiate XTTSBackend (which would load the model). A missing file
    # proves routing reached the XTTS branch without loading anything heavy.
    try:
        get_backend(profile)
    except FileNotFoundError as e:
        assert "Speaker WAV not found" in str(e)
        print("✅ Factory correctly routes to XTTSBackend (reference validation hit)")
        return
    raise AssertionError("Expected FileNotFoundError when routing XTTS with a missing reference")


def test_factory_rejects_unknown_backend():
    profile = VoiceProfile(backend_type="not-a-real-engine")
    try:
        get_backend(profile)
    except ValueError as e:
        assert "Unknown backend" in str(e)
        print("✅ Factory rejects unknown backend")
        return
    raise AssertionError("Expected ValueError for unknown backend")


if __name__ == "__main__":
    test_factory_routes_to_f5()
    test_factory_routes_to_xtts()
    test_factory_rejects_unknown_backend()
    print("✅ All routing tests passed.")
