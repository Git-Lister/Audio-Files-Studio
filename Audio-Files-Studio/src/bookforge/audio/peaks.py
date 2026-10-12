"""Waveform peak extraction for audio files."""

from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
from pathlib import Path

import soundfile as sf

TEMP_STUDIO_DIR = Path("temp/studio")


def get_duration(path: Path) -> float:
    """Return duration in seconds, via ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except Exception as e:
        raise RuntimeError(f"Failed to get duration for {path}: {e}") from e


def get_metadata(path: Path) -> dict:
    """Return {'duration': float, 'sample_rate': int, 'channels': int, 'size_mb': float}."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration,size:stream=sample_rate,channels",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        fmt = data.get("format", {})
        stream = data.get("streams", [{}])[0]
        return {
            "duration": float(fmt.get("duration", 0.0)),
            "sample_rate": int(stream.get("sample_rate", 0)),
            "channels": int(stream.get("channels", 0)),
            "size_mb": int(fmt.get("size", 0)) / (1024 * 1024),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to get metadata for {path}: {e}") from e


def extract_peaks(path: Path, target_buckets: int = 2000) -> list[tuple[float, float]]:
    """Return [(min, max), ...] pairs for waveform display.

    Peaks are normalised to the range [-1.0, 1.0].
    If the audio is shorter than target_buckets samples, returns one
    bucket per sample.
    """
    TEMP_STUDIO_DIR.mkdir(parents=True, exist_ok=True)

    temp_wav = TEMP_STUDIO_DIR / f"peaks_{uuid.uuid4().hex}.wav"

    try:
        # Convert to low-rate mono WAV for peak extraction
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-ac",
                "1",
                "-ar",
                "8000",
                "-c:a",
                "pcm_s16le",
                str(temp_wav),
            ],
            check=True,
            capture_output=True,
        )

        # Read with soundfile
        samples, _ = sf.read(temp_wav, dtype="float32")
        if len(samples) == 0:
            return []

        # Downsample to target_buckets
        n_samples = len(samples)
        if n_samples <= target_buckets:
            # One bucket per sample
            peaks = [(float(s), float(s)) for s in samples]
        else:
            # Reshape and take min/max per bucket
            bucket_size = n_samples // target_buckets
            peaks = []
            for i in range(target_buckets):
                start = i * bucket_size
                end = start + bucket_size
                bucket = samples[start:end]
                if len(bucket) > 0:
                    min_val = float(bucket.min())
                    max_val = float(bucket.max())
                    peaks.append((min_val, max_val))
                else:
                    peaks.append((0.0, 0.0))

        return peaks

    except Exception:
        return []
    finally:
        if temp_wav.exists():
            temp_wav.unlink()