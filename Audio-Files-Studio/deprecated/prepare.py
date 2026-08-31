"""
Prepare view – initiate text preparation and show chapter detection preview.
"""

from __future__ import annotations

import asyncio

from nicegui import ui

from bookforge.ui.components import get_processor, safe_notify


def view():
    container = ui.column().classes("w-full")
    with container:
        ui.label("2. Prepare Book").classes("text-h5 q-mb-md")
        prepare_status = ui.label("Press the button to analyse the book.")
        with ui.row().classes("items-center gap-4"):
            prepare_btn = ui.button("Prepare Book", icon="auto_stories")
            prepare_spinner = ui.spinner(size="md").props("color=primary")
            prepare_spinner.visible = False

        chapter_list_container = ui.column().classes("w-full")

        async def on_prepare():
            proc = get_processor()
            if proc is None:
                safe_notify("No configuration saved.", type="negative")
                return
            prepare_btn.disable()
            prepare_spinner.visible = True
            try:
                await asyncio.to_thread(proc.prepare_text)
                progress = proc.get_progress()
                prepare_status.set_text(f"✅ {progress.total_chapters} chapters found.")
                chapter_list_container.clear()
                with chapter_list_container:
                    ui.label("Detected chapters:").classes("font-bold")
                    for i, title in enumerate(proc.book_text.chapter_titles or []):
                        ui.label(f"{i + 1}. {title}").classes("text-caption")
                safe_notify("Book prepared!", type="positive")
                container.switch_to_synthesize()
            except Exception as e:  # noqa: BLE001
                safe_notify(f"Preparation failed: {e}", type="negative")
            finally:
                prepare_btn.enable()
                prepare_spinner.visible = False

        prepare_btn.on_click(lambda: on_prepare())

    container.switch_to_synthesize = None  # set by main
    return container
