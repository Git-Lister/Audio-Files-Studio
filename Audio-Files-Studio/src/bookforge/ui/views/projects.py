# src/bookforge/ui/views/projects.py
"""Projects view – three-state grid with appropriate actions for In Progress, Completed, and Empty projects."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from nicegui import ui

from bookforge.ui import state
from bookforge.ui import voice_library as vlib
from bookforge.ui.components import get_processor, safe_notify, set_processor


OUT_DIR = Path("out")


def _get_project_state(project_dir: Path) -> str:
    """Return 'complete', 'in_progress', or 'empty'."""
    has_book = (project_dir / "book.wav").exists()
    has_progress = (project_dir / "processing_progress.json").exists()
    if has_progress:
        return "in_progress"
    if has_book:
        return "complete"
    return "empty"


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def _resolve_voice_name(speaker_wav: str) -> str:
    """Extract voice_id from speaker_wav path and resolve to name."""
    if "user_voices/" in speaker_wav:
        try:
            voice_id = speaker_wav.split("user_voices/")[1].split("/")[0]
            v = vlib.get_voice(voice_id)
            if v:
                return v.get("name", "—")
        except IndexError:
            pass
    return "—"


def view():
    container = ui.column().classes("w-full")

    def refresh() -> None:
        container.clear()

        with container:
            ui.label("Projects").classes("text-h5 q-mb-md")

            if not OUT_DIR.exists():
                ui.label("No projects folder yet.").classes("text-grey")
                return

            projects = sorted(
                [p for p in OUT_DIR.iterdir() if p.is_dir()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            if not projects:
                ui.label(
                    "No projects yet. Start one from New Project."
                ).classes("text-grey")
                return

            grouped: dict[str, list[Path]] = {
                "in_progress": [],
                "complete": [],
                "empty": [],
            }
            for proj in projects:
                grouped[_get_project_state(proj)].append(proj)

            if grouped["in_progress"]:
                ui.label("In Progress").classes("text-h6 q-mt-md")
                for proj in grouped["in_progress"]:
                    _render_in_progress_card(proj, refresh)

            if grouped["complete"]:
                ui.label("Completed").classes("text-h6 q-mt-md")
                for proj in grouped["complete"]:
                    _render_complete_card(proj, refresh)

            if grouped["empty"]:
                ui.label("Empty / Failed").classes("text-h6 q-mt-md")
                for proj in grouped["empty"]:
                    _render_empty_card(proj, refresh)

    def _render_in_progress_card(project_dir: Path, on_change) -> None:
        progress = _read_json(project_dir / "processing_progress.json") or {}
        chapter_progress = progress.get("chapter_progress", [])
        total = len(chapter_progress)
        done = sum(1 for c in chapter_progress if c.get("chapter_audio_created"))

        source = Path(progress.get("input_file", "")).name or "—"
        voice_name = _resolve_voice_name(progress.get("speaker_wav", ""))

        with ui.card().classes("w-full q-mb-sm"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.label(project_dir.name).classes("text-h6")
                ui.label(f"{done}/{total} chapters").classes("text-caption text-grey")
            with ui.row().classes("gap-4 text-caption text-grey"):
                ui.label(f"Book: {source}")
                ui.label(f"Voice: {voice_name}")
            with ui.row().classes("gap-2 q-mt-sm"):
                ui.button(
                    "Resume",
                    icon="play_arrow",
                    on_click=lambda p=project_dir: _resume(p),
                ).props("color=primary size=sm")
                ui.button(
                    "Delete",
                    icon="delete",
                    on_click=lambda p=project_dir: _confirm_delete(p, on_change),
                ).props("flat color=negative size=sm")

    def _render_complete_card(project_dir: Path, on_change) -> None:
        book = project_dir / "book.wav"
        meta = _read_json(project_dir / "meta.json") or {}

        # Duration
        duration_str = "—"
        try:
            r = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(book)
                ],
                capture_output=True, text=True, timeout=10,
            )
            duration_str = _format_duration(float(r.stdout.strip()))
        except Exception:
            pass

        chapters = len(list((project_dir / "chapters").glob("chapter_*.wav"))) \
            if (project_dir / "chapters").exists() else 0

        voice_name = _resolve_voice_name(meta.get("speaker_wav", ""))

        completed_at = meta.get("processing_completed", "")
        if completed_at:
            try:
                dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                completed_at = dt.strftime("%d %b %Y")
            except ValueError:
                pass

        with ui.card().classes("w-full q-mb-sm"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.label(project_dir.name).classes("text-h6")
                ui.label(duration_str).classes("text-caption text-grey")
            with ui.row().classes("gap-4 text-caption text-grey"):
                ui.label(f"Chapters: {chapters}")
                ui.label(f"Voice: {voice_name}")
                if completed_at:
                    ui.label(f"Completed: {completed_at}")
            # Audio player for the book
            ui.audio(str(book)).classes("w-full q-mt-sm")
            with ui.row().classes("gap-2 q-mt-sm"):
                ui.button(
                    "Export M4B",
                    icon="download",
                    on_click=lambda p=project_dir: _export_m4b(p),
                ).props("flat color=secondary size=sm")
                ui.button(
                    "Delete",
                    icon="delete",
                    on_click=lambda p=project_dir: _confirm_delete(p, on_change),
                ).props("flat color=negative size=sm")

    def _render_empty_card(project_dir: Path, on_change) -> None:
        with ui.card().classes("w-full q-mb-sm"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.label(project_dir.name).classes("text-h6")
                ui.label("No audio, no progress").classes("text-caption text-grey")
            with ui.row().classes("gap-2 q-mt-sm"):
                ui.button(
                    "Delete",
                    icon="delete",
                    on_click=lambda p=project_dir: _confirm_delete(p, on_change),
                ).props("flat color=negative size=sm")

    async def _resume(project_dir: Path) -> None:
        cb = state.get_resume_callback()
        if cb is None:
            try:
                safe_notify("Resume not configured.", type="negative")
            except RuntimeError:
                pass
            return
        try:
            await cb(project_dir.name)
        except Exception as e:
            try:
                safe_notify(f"Resume failed: {e}", type="negative")
            except RuntimeError:
                pass

    def _confirm_delete(project_dir: Path, on_change) -> None:
        with ui.dialog() as dialog, ui.card().classes("max-w-md"):
            ui.label(f"Delete project '{project_dir.name}'?").classes("text-h6")
            ui.label(
                "This removes all files under out/. The action cannot be undone."
            ).classes("text-caption")

            def confirm() -> None:
                try:
                    shutil.rmtree(project_dir)
                    # Clear the active processor if it referenced this project
                    proc = get_processor()
                    if proc is not None and proc.output_dir == project_dir:
                        set_processor(None)
                    try:
                        safe_notify(f"Deleted '{project_dir.name}'", type="positive")
                    except RuntimeError:
                        pass
                    dialog.close()
                    on_change()
                except OSError as e:
                    try:
                        safe_notify(f"Delete failed: {e}", type="negative")
                    except RuntimeError:
                        pass

            with ui.row().classes("justify-end w-full q-mt-md gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Delete", on_click=confirm).props("color=negative")
        dialog.open()

    def _export_m4b(project_dir: Path) -> None:
        # Placeholder: full M4B re-export lives in the Pipeline
        try:
            safe_notify(
                "M4B re-export from Projects is not yet available. "
                "Open the project in Pipeline to export.",
                type="info",
            )
        except RuntimeError:
            pass

    refresh()
    return container