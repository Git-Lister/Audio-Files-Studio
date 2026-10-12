"""Destructive audio editing operations with snapshot-based undo support."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from .concat import concat_wavs

TEMP_STUDIO_DIR = Path("temp/studio")
SESSIONS_DIR = TEMP_STUDIO_DIR / "sessions"


def new_working_copy(source: Path) -> Path:
    """Copy source to a fresh working file under temp/studio/.

    Returns the working file path. Downmixes to a consistent format:
    44.1kHz stereo, 16-bit PCM WAV. This standardises the working format
    for all subsequent operations.
    """
    TEMP_STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    working = TEMP_STUDIO_DIR / f"working_{uuid.uuid4().hex}.wav"

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-ar",
            "44100",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(working),
        ],
        check=True,
        capture_output=True,
    )
    return working


def _ensure_session_dir() -> Path:
    """Create a new session directory for snapshots."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_dir = SESSIONS_DIR / uuid.uuid4().hex
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def snapshot(working: Path, session_dir: Path) -> Path:
    """Copy the working file into session_dir as a numbered snapshot.

    Returns the snapshot path.
    """
    existing = sorted(session_dir.glob("snap_*.wav"))
    next_num = len(existing) + 1
    snap_path = session_dir / f"snap_{next_num:04d}.wav"
    working.replace(snap_path)  # Move current working to snapshot
    return snap_path


def _run_ffmpeg(cmd: list[str]) -> None:
    """Run ffmpeg command, raising on failure."""
    subprocess.run(cmd, check=True, capture_output=True)


def trim(working: Path, start: float, end: float) -> None:
    """Trim working in place to [start, end] seconds.

    Non-destructive on failure: writes to a temp file first, then renames
    over the original.
    """
    if start >= end:
        raise ValueError("start must be less than end")

    temp_out = working.with_suffix(".trim.wav")
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(working),
            "-ss",
            str(start),
            "-to",
            str(end),
            "-c:a",
            "pcm_s16le",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(temp_out),
        ]
    )
    temp_out.replace(working)


def delete_range(working: Path, start: float, end: float) -> None:
    """Delete the [start, end] region and concatenate what remains.

    If deletion leaves nothing, raise ValueError.
    Uses concat_wavs from the existing audio.concatenate module.
    """
    if start >= end:
        raise ValueError("start must be less than end")

    # Get duration first
    duration_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(working),
    ]
    result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
    duration = float(result.stdout.strip())

    if start < 0 or end > duration:
        raise ValueError(f"Range [{start}, {end}] exceeds duration {duration}")

    part_before = working.with_suffix(".before.wav")
    part_after = working.with_suffix(".after.wav")

    try:
        has_before = False
        has_after = False

        if start > 0:
            _run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(working),
                    "-to",
                    str(start),
                    "-c:a",
                    "pcm_s16le",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    str(part_before),
                ]
            )
            has_before = True

        if end < duration:
            _run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(working),
                    "-ss",
                    str(end),
                    "-c:a",
                    "pcm_s16le",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    str(part_after),
                ]
            )
            has_after = True

        if has_before and has_after:
            concat_wavs([part_before, part_after], working)
        elif has_before:
            part_before.replace(working)
        elif has_after:
            part_after.replace(working)
        else:
            raise ValueError("Deletion would leave empty audio")

    finally:
        for p in (part_before, part_after):
            if p.exists():
                p.unlink()


def split_at(working: Path, position: float, output_dir: Path) -> tuple[Path, Path]:
    """Split working at position into two files in output_dir.

    Returns (left_path, right_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get duration
    duration_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(working),
    ]
    result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
    duration = float(result.stdout.strip())

    if position <= 0 or position >= duration:
        raise ValueError(f"Split position {position} must be in (0, {duration})")

    left_path = output_dir / "left.wav"
    right_path = output_dir / "right.wav"

    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(working),
            "-to",
            str(position),
            "-c:a",
            "pcm_s16le",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(left_path),
        ]
    )
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(working),
            "-ss",
            str(position),
            "-c:a",
            "pcm_s16le",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(right_path),
        ]
    )
    return left_path, right_path