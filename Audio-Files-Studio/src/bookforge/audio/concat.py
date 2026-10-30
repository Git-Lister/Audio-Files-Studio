"""Audio concatenation utilities for BookForge."""

from __future__ import annotations

import os
import subprocess
import uuid
from collections.abc import Iterable
from pathlib import Path

# Use BOOKFORGE_FFMPEG env var if set, otherwise just "ffmpeg" (works in Docker and on PATH)
FFMPEG_BIN = os.environ.get("BOOKFORGE_FFMPEG", "ffmpeg")


def concat_wavs(wav_paths: Iterable[Path], output_path: Path) -> None:
    """Concatenate multiple WAV files into a single WAV.

    Every input is first normalised to 24kHz mono 16-bit PCM so the concat
    demuxer never hits a sample-rate/channel mismatch, then the normalized
    files are joined via the concat demuxer with a list file (which also
    avoids Windows command-line length limits).
    """
    wav_list = [p for p in wav_paths if p.exists()]
    if not wav_list:
        raise ValueError("No WAV files to concatenate.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    list_file = output_path.with_suffix(".txt")
    normalized_paths: list[Path] = []

    try:
        # Step 1: Normalize all inputs to 24kHz mono 16-bit PCM.
        for p in wav_list:
            tmp = output_path.parent / f"norm_{p.stem}_{uuid.uuid4().hex[:4]}.wav"
            cmd = [
                FFMPEG_BIN,
                "-y",
                "-i",
                str(p),
                "-ar",
                "24000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(tmp),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                normalized_paths.append(tmp)
            except subprocess.CalledProcessError as e:
                stderr = e.stderr.decode(errors="ignore") if e.stderr else "(no stderr)"
                raise RuntimeError(
                    f"Format normalization failed for {p.name}: {stderr[-300:]}"
                )

        # Step 2: Concatenate using the normalized files.
        with list_file.open("w", encoding="utf-8") as f:
            for p in normalized_paths:
                abs_path = p.resolve()
                # Escape single quotes for ffmpeg
                path_str = abs_path.as_posix().replace("'", r"'\''")
                f.write(f"file '{path_str}'\n")

        cmd_concat = [
            FFMPEG_BIN,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(output_path),
        ]
        try:
            subprocess.run(cmd_concat, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors="ignore") if e.stderr else "(no stderr)"
            raise RuntimeError(f"FFmpeg concat failed: {stderr[-300:]}")
    finally:
        # Cleanup temporary files.
        if list_file.exists():
            list_file.unlink()
        for p in normalized_paths:
            if p.exists():
                p.unlink()
