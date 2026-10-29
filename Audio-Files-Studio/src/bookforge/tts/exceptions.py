"""Shared TTS exceptions."""

from __future__ import annotations


class CudaDeviceAssertError(RuntimeError):
    """Raised when the GPU context is corrupted by a NaN/Inf in the model."""
