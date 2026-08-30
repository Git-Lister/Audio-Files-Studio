"""Audio normalization utilities for BookForge."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

# Use BOOKFORGE_FFMPEG env var if set, otherwise just "ffmpeg" (works in Docker and on PATH)
FFMPEG_BIN = os.environ.get("BOOKFORGE_FFMPEG", "ffmpeg")


def normalize_audio(
    input_path: Path,
    output_path: Path,
    target_lufs: float = -16.0,
    loudness_range: float = 7.0,
) -> None:
    """
    Normalize audio using ffmpeg's loudnorm filter (EBU R128 standard).
    
    This is a two-pass process for accurate normalization:
    1. Analyze audio to measure current loudness
    2. Apply correction to reach target loudness
    
    Args:
        input_path: Source audio file
        output_path: Normalized output file
        target_lufs: Target integrated loudness in LUFS 
                     (-16.0 for audiobooks, -23.0 for broadcast)
        loudness_range: Target loudness range in LU (7.0 default)
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Pass 1: Analyze audio to measure current loudness
    cmd_analyze = [
        FFMPEG_BIN,
        "-i", str(input_path),
        "-af", f"loudnorm=I={target_lufs}:LRA={loudness_range}:print_format=json",
        "-f", "null",
        "-"
    ]
    
    result = subprocess.run(
        cmd_analyze,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg analysis failed: {result.stderr}")
    
    # Extract measured values from JSON output in stderr
    stderr = result.stderr
    json_start = stderr.rfind('{')
    json_end = stderr.rfind('}') + 1
    
    if json_start == -1 or json_end == 0:
        raise RuntimeError("Failed to parse loudness analysis JSON")
    
    measured = json.loads(stderr[json_start:json_end])
    
    # Pass 2: Normalize using measured values for accurate correction
    cmd_normalize = [
        FFMPEG_BIN,
        "-i", str(input_path),
        "-af", (
            f"loudnorm=I={target_lufs}:LRA={loudness_range}:"
            f"measured_I={measured['input_i']}:"
            f"measured_LRA={measured['input_lra']}:"
            f"measured_TP={measured['input_tp']}:"
            f"measured_thresh={measured['input_thresh']}:"
            f"offset={measured['target_offset']}:"
            "print_format=summary"
        ),
        "-y",
        str(output_path)
    ]
    
    result = subprocess.run(
        cmd_normalize,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg normalization failed: {result.stderr}")


def normalize_directory(
    input_dir: Path,
    output_dir: Path,
    pattern: str = "*.wav",
    target_lufs: float = -16.0,
) -> None:
    """
    Normalize all audio files in a directory.
    
    Useful for batch-normalizing chapter WAVs or chunks.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    files = list(input_dir.glob(pattern))
    if not files:
        raise ValueError(f"No files matching {pattern} found in {input_dir}")
    
    for i, input_file in enumerate(files, 1):
        output_file = output_dir / input_file.name
        print(f"Normalizing {i}/{len(files)}: {input_file.name}")
        normalize_audio(input_file, output_file, target_lufs=target_lufs)