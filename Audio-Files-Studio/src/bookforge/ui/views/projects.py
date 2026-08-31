# src/bookforge/ui/views/projects.py
"""Projects view – grid of project cards with actions."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from nicegui import ui

from bookforge.ui import state
from bookforge.ui.components import get_processor, safe_notify, set_processor


def view():
    container = ui.column().classes("w-full")
    projects_grid = ui.column().classes("w-full")

    async def load_projects():
        projects_grid.clear()
        with projects_grid:
            out_dir = Path("out")
            if not out_dir.exists():
                ui.label("No projects found.").classes("text-grey")
                return

            projects = [p for p in out_dir.iterdir() if p.is_dir() and (p / "meta.json").exists()]
            if not projects:
                ui.label("No completed or in‑progress projects.").classes("text-grey")
                return

            with ui.row().classes("w-full items-stretch gap-4"):
                for proj in sorted(
                    projects, key=lambda p: (p / "meta.json").stat().st_mtime, reverse=True
                ):
                    with ui.card().classes("col-12 col-sm-6 col-md-4"):
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label(proj.name).classes("text-h6")
                            status = _get_project_status(proj)
                            ui.label(status).classes("text-caption")
                        if status == "⏳ In progress":
                            progress_path = proj / "processing_progress.json"
                            if progress_path.exists():
                                try:
                                    with progress_path.open("r") as f:
                                        data = json.load(f)
                                    overall = data.get("overall_progress", 0)
                                    ui.linear_progress(value=overall).props(
                                        "size=10px color=primary"
                                    )
                                except:
                                    pass
                        with ui.row().classes("items-center gap-2 q-mt-sm"):
                            ui.button("Resume", on_click=lambda p=proj: _resume_project(p)).props(
                                "flat color=primary"
                            )
                            ui.button("Delete", on_click=lambda p=proj: _delete_project(p)).props(
                                "flat color=negative icon=delete"
                            )
                            if status == "✅ Completed":
                                m4b_path = proj / "book.m4b"
                                if m4b_path.exists():
                                    ui.button(
                                        "Export M4B",
                                        on_click=lambda p=proj: safe_notify(
                                            f"M4B already exists at {m4b_path}", type="positive"
                                        ),
                                    ).props("flat color=secondary")
                                else:
                                    ui.button(
                                        "Export M4B", on_click=lambda p=proj: _export_m4b(p)
                                    ).props("flat color=secondary")

    def _get_project_status(proj: Path) -> str:
        meta_path = proj / "meta.json"
        if not meta_path.exists():
            return "Unknown"
        with meta_path.open("r") as f:
            meta = json.load(f)
        if "processing_completed" in meta:
            return "✅ Completed"
        progress_path = proj / "processing_progress.json"
        if progress_path.exists():
            return "⏳ In progress"
        return "📄 Prepared"

    def _resume_project(proj: Path):
        callback = state.get_resume_callback()
        if callback:
            asyncio.create_task(callback(proj.name))
        else:
            safe_notify("Resume not configured.", type="warning")

    async def _delete_project(proj: Path):
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Delete project '{proj.name}'?").classes("text-h6")
            ui.label("This action cannot be undone.")
            with ui.row().classes("items-center gap-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Delete", on_click=lambda: _confirm_delete(proj, dialog)).props(
                    "color=negative"
                )
        dialog.open()

    def _confirm_delete(proj: Path, dialog):
        try:
            shutil.rmtree(proj)
            safe_notify(f"Deleted '{proj.name}'", type="positive")
            dialog.close()
            proc = get_processor()
            if proc and proc.output_dir == proj:
                set_processor(None)
            asyncio.create_task(load_projects())
        except Exception as e:
            safe_notify(f"Failed to delete: {e}", type="negative")

    async def _export_m4b(proj: Path):
        safe_notify(
            f"Export M4B for {proj.name} not yet implemented in Projects view", type="warning"
        )

    async def refresh():
        await load_projects()

    asyncio.create_task(load_projects())

    return container
