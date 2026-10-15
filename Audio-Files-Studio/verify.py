"""
Verification script for Audio-Files-Studio.

Runs a series of checks against the codebase and filesystem. Each check
prints PASS, FAIL, or INFO. At the end, a summary of failures.

Run inside the container:
    docker compose run --rm studio python verify.py
"""

from __future__ import annotations

import glob
import json
import re
import subprocess
import sys
from pathlib import Path

PASS = "PASS"
FAIL = "FAIL"
INFO = "INFO"

results: list[tuple[str, str, str]] = []  # (status, name, detail)


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    print(f"[{status}] {name}")
    if detail:
        for line in detail.split("\n"):
            print(f"       {line}")
    print()


def check_cleanup_dash_strip() -> None:
    """# markers must not survive sanitise_for_tts."""
    try:
        from bookforge.process.sanitize import sanitise_for_tts
    except Exception as e:
        record(FAIL, "sanitize import", str(e))
        return

    sample = "# Slide 1 — Title\n\nBody text."
    out = sanitise_for_tts(sample)
    if "#" in out:
        record(FAIL, "sanitize strips #", f"output still contains '#': {out!r}")
    else:
        record(PASS, "sanitize strips #", f"output: {out!r}")


def check_references_stripping() -> None:
    """strip_references_section should truncate at 'References'."""
    try:
        from bookforge.text_extract import clean, default_enabled_keys
    except Exception as e:
        record(FAIL, "cleanup import", str(e))
        return

    keys = default_enabled_keys() | {"strip_references_section"}
    text = (
        "Chapter One.\n\nSome prose here.\n\n"
        "References\n\nSmith, J. (2020). A book. Publisher.\n"
    )
    out = clean(text, keys)
    if "Smith, J." in out:
        record(FAIL, "strip_references_section",
               f"references still present:\n{out}")
    else:
        record(PASS, "strip_references_section",
               "references removed")


def check_research380() -> None:
    """RESEARCH380-style concatenation should be stripped."""
    try:
        from bookforge.text_extract import clean, default_enabled_keys
    except Exception as e:
        record(FAIL, "cleanup import", str(e))
        return

    text = "Intro paragraph.\n\nRESEARCH380\n\nBody text."
    out = clean(text, default_enabled_keys())
    if "RESEARCH380" in out:
        record(FAIL, "RESEARCH380 stripped", f"still present: {out!r}")
    else:
        record(PASS, "RESEARCH380 stripped", f"output: {out!r}")


def check_chapter_detector_skips_author() -> None:
    """First 20 lines should not be flagged as heuristic chapters."""
    try:
        from bookforge.process.chapter_detector import ChapterDetector
    except Exception as e:
        record(FAIL, "chapter_detector import", str(e))
        return

    text = (
        "Jarek Kaminski\nJoanna Ziemna\n\n"
        "Faculty of Philosophy\n\n"
        + ("Body text line.\n\n" * 30)
        + "Real Chapter\n\nMore body."
    )
    d = ChapterDetector()
    try:
        boundaries = d.detect(text, strategy="heuristic")
    except Exception as e:
        record(FAIL, "chapter_detector.detect", str(e))
        return

    early = [b for b in boundaries if b.line_index < 20]
    if early:
        record(FAIL, "chapter detector skips first 20 lines",
               f"found boundaries in first 20 lines: "
               f"{[(b.line_index, b.title) for b in early]}")
    else:
        record(PASS, "chapter detector skips first 20 lines",
               f"{len(boundaries)} boundaries, none in first 20 lines")


def _read_code(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def check_apad_present() -> None:
    """apad=pad_dur=0.5 must appear in xtts.py."""
    path = Path("src/bookforge/tts/xtts.py")
    if not path.exists():
        record(FAIL, "apad padding", f"{path} not found")
        return
    code = _read_code(path)
    if "apad=pad_dur" in code:
        match = re.search(r"apad=pad_dur=[\d.]+", code)
        record(PASS, "apad padding present",
               f"found: {match.group(0) if match else '?'}")
    else:
        record(FAIL, "apad padding present",
               "no 'apad=pad_dur' in xtts.py")


def check_preflight_stale_chunks() -> None:
    """Pre-flight check for stale chapter progress must exist."""
    path = Path("src/bookforge/incremental_processor.py")
    if not path.exists():
        record(FAIL, "preflight check", f"{path} not found")
        return
    code = _read_code(path)
    if "Resetting chapter" in code or "WAV files missing" in code:
        record(PASS, "preflight stale-chunk check present",
               "found reset logic in incremental_processor.py")
    else:
        record(FAIL, "preflight stale-chunk check present",
               "no reset logic found")


def check_resume_await_not_task() -> None:
    """resume_project must be awaited, not launched as a task."""
    path = Path("src/bookforge/ui/views/projects.py")
    if not path.exists():
        record(INFO, "resume_project code path",
               f"{path} not found; check the actual file")
        return

    code = _read_code(path)
    task_calls = re.findall(r"asyncio\.create_task\(\s*[^)]*resume[^)]*\)", code)
    if task_calls:
        record(FAIL, "resume_project uses create_task",
               f"found: {task_calls}")
    elif "await" in code and "resume" in code:
        record(PASS, "resume_project uses await",
               "found 'await' referencing resume")
    else:
        record(INFO, "resume_project code path",
               "could not confirm; manual check needed")


def check_tooltips_wizard() -> None:
    path = Path("src/bookforge/ui/views/wizard.py")
    code = _read_code(path)
    n = code.count("ui.tooltip(")
    if n >= 3:
        record(PASS, "wizard tooltips", f"{n} tooltips found")
    else:
        record(FAIL, "wizard tooltips", f"only {n} tooltips found (need ≥3)")


def check_tooltips_settings() -> None:
    path = Path("src/bookforge/ui/views/settings.py")
    code = _read_code(path)
    n = code.count("ui.tooltip(")
    if n >= 2:
        record(PASS, "settings tooltips", f"{n} tooltips found")
    else:
        record(FAIL, "settings tooltips", f"only {n} tooltips found (need ≥2)")


def check_project_dirs() -> None:
    """List projects with/without progress files so user can pick one to test."""
    out_root = Path("out")
    if not out_root.exists():
        record(INFO, "projects on disk", "out/ does not exist")
        return

    lines = []
    for proj in sorted(out_root.iterdir()):
        if not proj.is_dir():
            continue
        prog = proj / "processing_progress.json"
        book = proj / "book.wav"
        meta = proj / "meta.json"
        lines.append(
            f"  {proj.name}: "
            f"progress={prog.exists()} "
            f"book.wav={book.exists()} "
            f"meta.json={meta.exists()}"
        )

    if lines:
        record(INFO, "projects on disk", "\n".join(lines))
    else:
        record(INFO, "projects on disk", "no project folders found")


def check_audio_metadata() -> None:
    """For each out/<proj>/book.wav, report duration and size."""
    wavs = glob.glob("out/*/book.wav")
    if not wavs:
        record(INFO, "book.wav files", "none found in out/")
        return

    lines = []
    for wav in sorted(wavs):
        try:
            out = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    wav,
                ],
                capture_output=True, text=True, timeout=10,
            )
            dur = float(out.stdout.strip()) if out.stdout.strip() else 0.0
            size_mb = Path(wav).stat().st_size / (1024 * 1024)
            lines.append(f"  {wav}: {dur:.1f}s, {size_mb:.1f} MB")
        except Exception as e:
            lines.append(f"  {wav}: ffprobe failed — {e}")

    record(INFO, "book.wav files", "\n".join(lines))


def main() -> int:
    print("=" * 60)
    print("Audio-Files-Studio verification")
    print("=" * 60)
    print()

    print("--- Cleanup rules ---")
    check_cleanup_dash_strip()
    check_references_stripping()
    check_research380()

    print("--- Chapter detection ---")
    check_chapter_detector_skips_author()

    print("--- Audio pipeline ---")
    check_apad_present()
    check_preflight_stale_chunks()

    print("--- Resume flow ---")
    check_resume_await_not_task()

    print("--- UI ---")
    check_tooltips_wizard()
    check_tooltips_settings()

    print("--- Filesystem state ---")
    check_project_dirs()
    check_audio_metadata()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    n_pass = sum(1 for s, _, _ in results if s == PASS)
    n_fail = sum(1 for s, _, _ in results if s == FAIL)
    n_info = sum(1 for s, _, _ in results if s == INFO)
    print(f"PASS: {n_pass}    FAIL: {n_fail}    INFO: {n_info}")
    print()

    if n_fail:
        print("Failures:")
        for s, name, detail in results:
            if s == FAIL:
                print(f"  - {name}")
                if detail:
                    for line in detail.split("\n"):
                        print(f"      {line}")
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())