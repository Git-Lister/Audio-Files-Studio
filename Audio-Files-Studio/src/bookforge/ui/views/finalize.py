# src/bookforge/ui/views/finalize.py
"""Finalize view – generate book.wav and export options."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

from nicegui import ui

from bookforge.ui.components import get_processor, safe_notify


def view():
    """Build the Finalize view."""
    container = ui.column().classes("w-full")

    # ---- Define functions BEFORE building UI ----
    async def finalize():
        proc = get_processor()
        if proc is None:
            safe_notify("No active project.", type="warning")
            return
        if not proc.is_complete():
            safe_notify("Book is not fully synthesized yet.", type="warning")
            return
        try:
            await asyncio.to_thread(proc.finalize_book)
            safe_notify("book.wav created!", type="positive")
            status_label.set_text("Book finalized. You can now export to M4B.")
            export_btn.visible = True
            book_wav = proc.output_dir / "book.wav"
            if book_wav.exists():
                audio_player.set_source(str(book_wav))
        except Exception as e:
            safe_notify(f"Finalization failed: {e}", type="negative")

    async def export_m4b():
        proc = get_processor()
        if proc is None:
            safe_notify("No active project.", type="warning")
            return
        book_wav = proc.output_dir / "book.wav"
        if not book_wav.exists():
            safe_notify("book.wav not found. Run finalize first.", type="warning")
            return

        meta_path = proc.output_dir / "meta.json"
        if not meta_path.exists():
            safe_notify("meta.json not found.", type="negative")
            return
        with meta_path.open("r") as f:
            meta = json.load(f)

        chapter_titles = meta.get("chapter_titles", [])
        if not chapter_titles:
            chapter_titles = [f"Chapter {i + 1}" for i in range(len(chapter_titles))]

        chapters_dir = proc.output_dir / "chapters"
        chapter_files = sorted(chapters_dir.glob("chapter_*.wav"))
        if not chapter_files:
            safe_notify("No chapter files found.", type="negative")
            return

        times = [0.0]
        for cf in chapter_files[:-1]:
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        str(cf),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                duration = float(result.stdout.strip())
                times.append(times[-1] + duration)
            except Exception as e:
                safe_notify(f"Failed to get duration for {cf.name}: {e}", type="warning")
                times.append(times[-1] + 60.0)

        chapter_file = proc.output_dir / "chapters.txt"
        with chapter_file.open("w") as f:
            for i, (title, start) in enumerate(zip(chapter_titles, times)):
                f.write(f"CHAPTER{i + 1:02d}={start:.3f}\n")
                f.write(f"CHAPTER{i + 1:02d}NAME={title}\n")

        m4b_path = proc.output_dir / "book.m4b"
        try:
            await asyncio.to_thread(
                subprocess.run,
                [
                    "ffmpeg",
                    "-i",
                    str(book_wav),
                    "-i",
                    str(chapter_file),
                    "-map_metadata",
                    "1",
                    "-map_chapters",
                    "1",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    str(m4b_path),
                    "-y",
                ],
                check=True,
                capture_output=True,
            )
            safe_notify(f"M4B exported: {m4b_path.name}", type="positive")
        except Exception as e:
            safe_notify(f"M4B export failed: {e}", type="negative")

    # ---- Build UI ----
    with container:
        ui.label("4. Finalize").classes("text-h5 q-mb-md")
        ui.markdown("Generate the final audiobook and export to different formats.")

        status_label = ui.label("Waiting for synthesis to complete...").classes("text-caption")
        finalize_btn = ui.button("Generate book.wav", on_click=finalize).props(
            "unelevated color=primary"
        )
        export_btn = ui.button("Export M4B", on_click=export_m4b).props(
            "unelevated color=secondary"
        )
        export_btn.visible = False

        audio_player = ui.audio("").classes("w-full q-mt-md")

    container.visible = False
    return container
