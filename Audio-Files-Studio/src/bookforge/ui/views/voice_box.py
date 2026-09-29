# src/bookforge/ui/views/voice_box.py
"""Voice Box (Gallery) – browse, search, play, and manage voice presets."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from nicegui import ui

from bookforge.ui import voice_library as lib
from bookforge.ui.components import safe_notify


def view(switch_to_vocalizer_callback=None):
    container = ui.column().classes("w-full")
    # Store the callback on the container for use in edit_voice
    container.switch_to_vocalizer = switch_to_vocalizer_callback

    with container:
        ui.label("📦 Voice Box (Gallery)").classes("text-h5 q-mb-md")
        ui.markdown("Browse your saved voices. Click **Edit** to open the Vocalizer and fine‑tune.")

        search_input = (
            ui.input(label="Search voices", placeholder="Filter by name or tags...")
            .props("outlined")
            .classes("w-full q-mb-md")
        )
        ui.button(icon="refresh", on_click=lambda: refresh()).props("flat").classes("q-ml-sm")

        grid = ui.column().classes("w-full items-stretch gap-4")

        def refresh():
            grid.clear()
            with grid:
                voices = lib.list_voices(system=None)
                search_term = search_input.value.strip().lower() if search_input.value else ""
                if search_term:
                    voices = [
                        v
                        for v in voices
                        if search_term in v["name"].lower()
                        or (v.get("tags", "") and search_term in v["tags"].lower())
                    ]
                if not voices:
                    ui.label("No voices found.").classes("text-grey")
                    return
                with ui.row().classes("w-full items-stretch gap-4"):
                    for voice in voices:
                        with ui.card().classes("col-12 col-sm-6 col-md-4"):
                            with ui.row().classes("items-center justify-between w-full"):
                                ui.label(voice["name"]).classes("text-h6")
                                if voice["is_system"]:
                                    ui.label("built‑in").classes("text-caption text-grey")
                            if voice.get("tags"):
                                ui.label(voice["tags"]).classes("text-caption text-grey")
                            audio = ui.audio("").classes("hidden w-full q-mt-sm")
                            with ui.row().classes("items-center gap-2 q-mt-sm"):
                                play_btn = ui.button(
                                    icon="play_arrow",
                                    on_click=lambda v=voice, a=audio: play_voice(v, a),
                                ).props("flat size=sm")
                                ui.button(
                                    icon="edit", on_click=lambda v=voice: edit_voice(v["id"])
                                ).props("flat size=sm")
                                if not voice["is_system"]:
                                    ui.button(
                                        icon="delete", on_click=lambda v=voice: delete_voice(v)
                                    ).props("flat color=negative size=sm")
                                    ui.button(
                                        icon="archive", on_click=lambda v=voice: export_voice(v)
                                    ).props("flat size=sm")

            with ui.row().classes("q-mb-md"):
                ui.button("Import Voice", icon="file_upload", on_click=import_voice).props(
                    "flat color=primary"
                )

        async def play_voice(voice, audio_element):
            """Play the voice's baked preview WAV, if it exists."""
            preview_path = lib.get_preview_path(voice["id"])
            if preview_path.exists():
                try:
                    audio_element.set_source(str(preview_path))
                    audio_element.classes(remove="hidden")
                except RuntimeError:
                    # Element was deleted (user navigated away)
                    pass
            else:
                safe_notify(
                    f"No preview baked for '{voice['name']}'. "
                    f"Edit and save the voice to generate one.",
                    type="warning",
                )

        def edit_voice(voice_id):
            from nicegui import app

            app.storage.general["edit_voice_id"] = voice_id
            # Use the callback stored on container
            if container.switch_to_vocalizer:
                container.switch_to_vocalizer()
            else:
                safe_notify("Navigation not configured.", type="warning")

        async def delete_voice(voice):
            with ui.dialog() as dialog, ui.card():
                ui.label(f"Delete voice '{voice['name']}'?").classes("text-h6")
                ui.label("This action cannot be undone.")
                with ui.row().classes("items-center gap-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Delete", on_click=lambda: confirm_delete(voice, dialog)).props(
                        "color=negative"
                    )
            dialog.open()

        def confirm_delete(voice, dialog):
            if lib.delete_voice(voice["id"]):
                safe_notify(f"Deleted '{voice['name']}'", type="positive")
                dialog.close()
                refresh()
            else:
                safe_notify("Failed to delete voice.", type="negative")

        async def export_voice(voice):
            """Export a voice to a .voice.zip and stream it to the browser."""
            try:
                tmp_dir = Path("temp")
                tmp_dir.mkdir(exist_ok=True)
                zip_path = tmp_dir / f"{voice['id']}.voice.zip"
                lib.export_voice(voice["id"], zip_path)
                ui.download.file(
                    zip_path,
                    filename=f"{voice['name']}.voice.zip",
                )
                safe_notify(f"Exported '{voice['name']}'", type="positive")
            except Exception as e:
                safe_notify(f"Export failed: {e}", type="negative")

        async def import_voice():
            with ui.dialog() as dialog, ui.card():
                ui.label("Import Voice").classes("text-h6")
                ui.markdown("Select a `.voice.zip` file exported from another instance.")
                ui.upload(
                    label="Upload .zip file",
                    on_upload=lambda e: asyncio.create_task(handle_import(e, dialog)),
                ).props("accept=.zip")
                ui.button("Cancel", on_click=dialog.close).props("flat")
            dialog.open()

        async def handle_import(e, dialog):
            try:
                temp_zip = (
                    Path("temp") / f"import_{int(datetime.now(timezone.utc).timestamp())}.zip"
                )
                temp_zip.parent.mkdir(exist_ok=True)
                content = await e.file.read()
                with open(temp_zip, "wb") as f:
                    f.write(content)
                new_id = lib.import_voice(temp_zip)
                if lib.get_preview_path(new_id).exists():
                    safe_notify(f"Imported voice '{new_id}' with preview.", type="positive")
                else:
                    safe_notify(
                        f"Imported voice with ID {new_id}. "
                        f"No preview in the archive -- edit and save the voice to bake one.",
                        type="warning",
                    )
                dialog.close()
                refresh()
            except Exception as err:
                safe_notify(f"Import failed: {err}", type="negative")

        # Initial load
        refresh()
        search_input.on_value_change(lambda: refresh())

    return container
