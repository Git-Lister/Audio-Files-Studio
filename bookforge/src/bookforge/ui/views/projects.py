"""
Projects view – list, review, resume, and delete projects.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from nicegui import ui

from bookforge.ui.components import safe_notify


def view():
    container = ui.column().classes("w-full")
    with container:
        ui.label("📚 My Projects").classes("text-h5")
        with ui.row().classes("items-center gap-2 q-mb-md"):
            project_select = ui.select(
                label="Select a project",
                options=[""] + sorted([p.name for p in Path("out").iterdir() if p.is_dir()]),
                on_change=lambda e: refresh_review(e.value),
            ).classes("flex-grow")
            ui.button(
                "Refresh list", icon="refresh", on_click=lambda: refresh_project_list()
            ).props("flat")

        review_area = ui.column()

        def refresh_project_list():
            project_select.options = [""] + sorted(
                [p.name for p in Path("out").iterdir() if p.is_dir()]
            )
            project_select.value = ""
            review_area.clear()

        def refresh_review(project_name: str):
            review_area.clear()
            if not project_name:
                return
            project_path = Path("out") / project_name
            is_incomplete = (project_path / "processing_progress.json").exists() and not (
                project_path / "meta.json"
            ).exists()
            with review_area:
                if is_incomplete:
                    ui.label("⚠️ This project is **incomplete**.").classes("text-orange q-mb-sm")
                    ui.button(
                        "Resume Processing", on_click=lambda p=project_name: container.on_resume(p)
                    ).props("color=orange icon=play_arrow")
                    ui.separator()
                else:
                    meta_path = project_path / "meta.json"
                    meta = {}
                    if meta_path.exists():
                        try:
                            with meta_path.open("r") as f:
                                meta = json.load(f)
                            ui.label(f"Backend: {meta.get('backend', '?')}").classes("text-caption")
                        except OSError as e:
                            safe_notify(f"Failed to read metadata: {e}", type="negative")
                    book_wav = project_path / "book.wav"
                    if book_wav.exists():
                        ui.audio(str(book_wav)).classes("w-full")
                    chapters = sorted(project_path.glob("chapters/*.wav"))
                    chapter_titles = meta.get("chapter_titles", [])
                    for idx, ch in enumerate(chapters):
                        title = chapter_titles[idx] if idx < len(chapter_titles) else ch.stem
                        with ui.expansion(title, icon="menu_book").classes("w-full"):
                            ui.audio(str(ch))
                    ui.button(
                        "Delete Project", on_click=lambda p=project_name: delete_project(p)
                    ).props("color=negative flat icon=delete")
                    ui.tooltip("Delete this project permanently")

        def delete_project(project_name: str):
            project_path = Path("out") / project_name
            if project_path.exists():
                shutil.rmtree(project_path)
                safe_notify(f"Deleted '{project_name}'", type="warning")
                refresh_project_list()

    container.on_resume = None
    return container
