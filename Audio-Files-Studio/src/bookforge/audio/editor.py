"""Destructive audio editing operations with snapshot-based undo support."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from .concat import concat_wavs
from .peaks import get_duration

TEMP_STUDIO_DIR = Path("temp/studio")
SESSIONS_DIR = TEMP_STUDIO_DIR / "sessions"


def new_session_dir() -> Path:
    """Create and return a fresh session directory under temp/studio/sessions/."""
    import uuid as _uuid
    session_id = _uuid.uuid4().hex[:12]
    session_dir = TEMP_STUDIO_DIR / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir.resolve()


def new_working_copy(source: Path, session_dir: Path | None = None) -> Path:
    """Copy source to a fresh working file under temp/studio/sessions/<session_id>/.

    Returns the working file path. Downmixes to a consistent format:
    44.1kHz stereo, 16-bit PCM WAV. This standardises the working format
    for all subsequent operations.
    """
    if session_dir is None:
        session_dir = new_session_dir()
    
    working_path = session_dir / "working.wav"

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
            str(working_path),
        ],
        check=True,
        capture_output=True,
    )
    
    # --- Diagnostic: verify creation and list the directory ---
    print(f"[AudioStudio.editor] new_working_copy returning: {working_path}")
    print(f"[AudioStudio.editor]   exists: {working_path.exists()}")
    print(f"[AudioStudio.editor]   absolute: {working_path.resolve()}")
    print(f"[AudioStudio.editor]   cwd: {Path.cwd()}")
    try:
        files = sorted(TEMP_STUDIO_DIR.glob("*"))
        print(f"[AudioStudio.editor]   temp/studio contents ({len(files)} files):")
        for f in files:
            print(f"[AudioStudio.editor]     {f.name} ({f.stat().st_size} bytes)")
    except Exception as e:
        print(f"[AudioStudio.editor]   could not list temp/studio: {e}")
    
    return working_path.resolve()


def _ensure_session_dir() -> Path:
    """Create a new session directory for snapshots."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_dir = SESSIONS_DIR / uuid.uuid4().hex
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def snapshot(working: Path, session_dir: Path) -> Path:
    """Copy the working file into session_dir/snapshots/ as a numbered snapshot.

    COPY (not move) so the working file remains in place for the operation
    that will follow. Returns the absolute path of the snapshot file.
    """
    import shutil as _shutil

    snapshots_dir = session_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    # Next sequential number
    existing = sorted(snapshots_dir.glob("snap_*.wav"))
    next_num = len(existing) + 1
    snapshot_path = snapshots_dir / f"snap_{next_num:04d}.wav"

    print(f"[AudioStudio.editor] snapshot: copying {working} -> {snapshot_path}")
    print(f"[AudioStudio.editor]   source exists: {working.exists()}")

    _shutil.copy(working, snapshot_path)

    print(f"[AudioStudio.editor]   snapshot exists after copy: {snapshot_path.exists()}")
    print(f"[AudioStudio.editor]   source still exists: {working.exists()}")

    return snapshot_path.resolve()


def _run_ffmpeg(cmd: list[str]) -> None:
    """Run ffmpeg command, raising on failure."""
    subprocess.run(cmd, check=True, capture_output=True)


def trim(working: Path, start: float, end: float) -> None:
    """Trim working in place to [start, end] seconds.

    Uses input seeking (`-ss` before `-i`) and an explicit duration
    (`-t`) so the interpretation is unambiguous across ffmpeg versions.
    Writes to a temp file first, then renames over the original.
    """
    print(f"[AudioStudio.editor] trim called: working={working}")
    print(f"[AudioStudio.editor]   exists: {working.exists()}")
    print(f"[AudioStudio.editor]   absolute: {working.resolve()}")
    print(f"[AudioStudio.editor]   cwd: {Path.cwd()}")
    try:
        files = sorted(Path("temp/studio").glob("*"))
        print(f"[AudioStudio.editor]   temp/studio contents ({len(files)} files):")
        for f in files:
            print(f"[AudioStudio.editor]     {f.name} ({f.stat().st_size} bytes)")
    except Exception as e:
        print(f"[AudioStudio.editor]   could not list temp/studio: {e}")
    
    if end <= start:
        raise ValueError(f"Invalid trim range: start={start}, end={end}")
    if not working.exists():
        raise FileNotFoundError(f"Working file not found: {working}")

    duration = end - start
    tmp = working.parent / f"{working.stem}.trim.wav"

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{start:.6f}",
        "-i", str(working),
        "-t", f"{duration:.6f}",
        "-c:a", "pcm_s16le",
        "-ar", "44100",
        "-ac", "2",
        str(tmp),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="ignore") if e.stderr else "(no stderr)"
        raise RuntimeError(
            f"ffmpeg trim failed (exit {e.returncode}): {stderr[-500:]}"
        ) from e
    except FileNotFoundError as e:
        raise RuntimeError(f"ffmpeg not found: {e}") from e

    tmp.rename(working)


def delete_range(working: Path, start: float, end: float) -> None:
    """Delete the [start, end] region and concatenate what remains.

    Extracts the before and after portions, then concatenates them.
    If either portion is empty, only the other is retained.
    """
    print(f"[AudioStudio.editor] delete_range called: working={working}")
    print(f"[AudioStudio.editor]   exists: {working.exists()}")
    print(f"[AudioStudio.editor]   absolute: {working.resolve()}")
    print(f"[AudioStudio.editor]   cwd: {Path.cwd()}")
    try:
        files = sorted(Path("temp/studio").glob("*"))
        print(f"[AudioStudio.editor]   temp/studio contents ({len(files)} files):")
        for f in files:
            print(f"[AudioStudio.editor]     {f.name} ({f.stat().st_size} bytes)")
    except Exception as e:
        print(f"[AudioStudio.editor]   could not list temp/studio: {e}")
    
    if end <= start:
        raise ValueError(f"Invalid delete range: start={start}, end={end}")
    if not working.exists():
        raise FileNotFoundError(f"Working file not found: {working}")

    parent = working.parent
    before = parent / f"{working.stem}.before.wav"
    after = parent / f"{working.stem}.after.wav"

    # Extract before
    if start > 0:
        cmd_before = [
            "ffmpeg", "-y",
            "-i", str(working),
            "-t", f"{start:.6f}",
            "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2",
            str(before),
        ]
        try:
            subprocess.run(cmd_before, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors="ignore") if e.stderr else "(no stderr)"
            raise RuntimeError(
                f"ffmpeg extract-before failed (exit {e.returncode}): {stderr[-500:]}"
            ) from e

    # Extract after
    cmd_after = [
        "ffmpeg", "-y",
        "-ss", f"{end:.6f}",
        "-i", str(working),
        "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2",
        str(after),
    ]
    try:
        subprocess.run(cmd_after, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="ignore") if e.stderr else "(no stderr)"
        raise RuntimeError(
            f"ffmpeg extract-after failed (exit {e.returncode}): {stderr[-500:]}"
        ) from e

    # If we had both parts, concatenate them. Otherwise, use whichever exists.
    if before.exists() and after.exists():
        concat_wavs([before, after], working)
        before.unlink(missing_ok=True)
        after.unlink(missing_ok=True)
    elif after.exists():
        after.replace(working)
    elif before.exists():
        before.replace(working)
    else:
        # Nothing to keep -- delete_range removed the whole file
        working.unlink(missing_ok=True)
        raise RuntimeError("Delete range removed the entire file")


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


def normalize_loudness(working: Path) -> None:
    """Normalize audio to EBU R128 (-16 LUFS)."""
    tmp = working.parent / f"{working.stem}.norm.wav"
    cmd = [
        "ffmpeg", "-y", "-i", str(working),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:a", "pcm_s16le", str(tmp)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="ignore") if e.stderr else "(no stderr)"
        raise RuntimeError(f"ffmpeg normalize failed: {stderr[-500:]}")
    tmp.rename(working)


def trim_silence(working: Path) -> None:
    """Trim leading/trailing silence and remove silences > 1s in the middle."""
    tmp = working.parent / f"{working.stem}.silence.wav"
    # Threshold -40dB, remove silences longer than 1.0s, leave 0.3s of padding
    af = "silenceremove=start_periods=1:start_duration=0.1:start_threshold=-40dB,areverse,silenceremove=start_periods=1:start_duration=0.1:start_threshold=-40dB,areverse"
    cmd = [
        "ffmpeg", "-y", "-i", str(working),
        "-af", af,
        "-c:a", "pcm_s16le", str(tmp)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="ignore") if e.stderr else "(no stderr)"
        raise RuntimeError(f"ffmpeg trim_silence failed: {stderr[-500:]}")
    tmp.rename(working)


def apply_fade(working: Path, direction: str, duration: float = 1.0) -> None:
    """Apply a fade in or fade out."""
    tmp = working.parent / f"{working.stem}.fade.wav"
    af = f"afade=t={direction}:st=0:d={duration}"
    if direction == "out":
        # For fade out, we need to start at (duration - fade_duration)
        total_dur = get_duration(working)
        start = max(0, total_dur - duration)
        af = f"afade=t=out:st={start}:d={duration}"

    cmd = [
        "ffmpeg", "-y", "-i", str(working),
        "-af", af, "-c:a", "pcm_s16le", str(tmp)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="ignore") if e.stderr else "(no stderr)"
        raise RuntimeError(f"ffmpeg fade failed: {stderr[-500:]}")
    tmp.rename(working)