"""Audio concatenation utilities for BookForge."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

import ffmpeg  # type: ignore[import]

# Use BOOKFORGE_FFMPEG env var if set, otherwise just "ffmpeg" (works in Docker and on PATH)
FFMPEG_BIN = os.environ.get("BOOKFORGE_FFMPEG", "ffmpeg")


def concat_wavs(wav_paths: Iterable[Path], output_path: Path) -> None:
    """Concatenate multiple WAV files into a single WAV using ffmpeg concat demuxer.

    This avoids Windows command-line length limits by using a list file.
    """
    wav_list: List[Path] = [p for p in wav_paths if p.exists()]
    if not wav_list:
        raise ValueError("No WAV files to concatenate.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    list_file = output_path.with_suffix(output_path.suffix + ".txt")

    # Write the list file in the format required by ffmpeg concat demuxer:
    # file '/full/path/to/file1.wav'
    # file '/full/path/to/file2.wav'
    with list_file.open("w", encoding="utf-8") as f:
        for p in wav_list:
            abs_path = p.resolve()
            # Escape single quotes for ffmpeg
            path_str = abs_path.as_posix().replace("'", r"'\''")
            f.write(f"file '{path_str}'\n")

    (
        ffmpeg
        .input(str(list_file), format="concat", safe=0)
        .output(str(output_path), acodec="copy")
        .overwrite_output()
        .run(cmd=FFMPEG_BIN, quiet=True)
    )