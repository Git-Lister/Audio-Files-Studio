# src/bookforge/ui/views/projects.py
"""Projects view – list all projects with resume and delete."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from nicegui import ui

from bookforge.ui.components import get_processor, safe_notify, set_processor


def view():
    """Build the Projects view and return a container with a refresh() method."""
    container = ui.column().classes("w-full")
    projects_list = ui.column().classes("w-full")

    async def load_projects():
        projects_list.clear()
        with projects_list:
            out_dir = Path("out")
            if not out_dir.exists():
                ui.label("No projects found.").classes("text-grey")
                return

            projects = [p for p in out_dir.iterdir() if p.is_dir() and (p / "meta.json").exists()]
            if not projects:
                ui.label("No completed or in‑progress projects.").classes("text-grey")
                return

            for proj in sorted(
                projects, key=lambda p: (p / "meta.json").stat().st_mtime, reverse=True
            ):
                with ui.card().classes("w-full q-mb-md"):
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label(proj.name).classes("text-h6")
                        status = _get_project_status(proj)
                        ui.label(status).classes("text-caption")

                    with ui.row().classes("items-center gap-2"):
                        ui.button("Resume", on_click=lambda p=proj: _resume_project(p)).props(
                            "flat color=primary"
                        )
                        ui.button("Delete", on_click=lambda p=proj: _delete_project(p)).props(
                            "flat color=negative icon=delete"
                        )

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

    async def _resume_project(proj: Path):
        if hasattr(container, "on_resume") and container.on_resume:
            await container.on_resume(proj.name)
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

    async def refresh():
        await load_projects()

    asyncio.create_task(load_projects())

    container.refresh = refresh
    container.on_resume = None  # will be set by main.py

    return container
