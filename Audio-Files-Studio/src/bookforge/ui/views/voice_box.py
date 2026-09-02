# src/bookforge/ui/views/voice_box.py
"""Voice Box (Gallery) – browse, search, play, and manage voice presets."""

from __future__ import annotations

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
                            with ui.row().classes("items-center gap-2 q-mt-sm"):
                                play_btn = ui.button(
                                    icon="play_arrow", on_click=lambda v=voice: play_voice(v)
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
                            audio = ui.audio("").classes("hidden w-full q-mt-sm")
                            setattr(play_btn, "_audio", audio)
                            setattr(play_btn, "_voice", voice)

            with ui.row().classes("q-mb-md"):
                ui.button("Import Voice", icon="file_upload", on_click=import_voice).props(
                    "flat color=primary"
                )

        async def play_voice(voice):
            from bookforge.ui.views.vocalizer import generate_preview

            audio = getattr(voice, "_audio", None)
            if audio is None:
                safe_notify("Playback not available for this voice.", type="warning")
                return
            try:
                wav_path = await generate_preview(
                    text=voice.get(
                        "preview_text",
                        "This is a sample of my voice. It is clear, natural, and ready for narration.",
                    ),
                    params={
                        "temperature": voice["temperature"],
                        "length_penalty": voice["length_penalty"],
                        "repetition_penalty": voice["repetition_penalty"],
                        "top_p": voice["top_p"],
                        "top_k": voice["top_k"],
                        "language": voice.get("language", "en"),
                        "reference_wav": voice.get("reference_wav_path"),
                    },
                )
                audio.set_source(str(wav_path))
                audio.classes(remove="hidden")
                safe_notify("Preview ready!", type="positive")
            except Exception as e:
                safe_notify(f"Preview generation failed: {e}", type="negative")

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
            download_path = Path.home() / "Downloads" / f"{voice['name']}.voice.zip"
            try:
                lib.export_voice(voice["id"], download_path)
                safe_notify(f"Exported to {download_path}", type="positive")
            except Exception as e:
                safe_notify(f"Export failed: {e}", type="negative")

        async def import_voice():
            with ui.dialog() as dialog, ui.card():
                ui.label("Import Voice").classes("text-h6")
                ui.markdown("Select a `.voice.zip` file exported from another instance.")
                ui.upload(
                    label="Upload .zip file", on_upload=lambda e: handle_import(e, dialog)
                ).props("accept=.zip")
                ui.button("Cancel", on_click=dialog.close).props("flat")
            dialog.open()

        def handle_import(e, dialog):
            try:
                temp_zip = (
                    Path("temp") / f"import_{int(datetime.now(timezone.utc).timestamp())}.zip"
                )
                temp_zip.parent.mkdir(exist_ok=True)
                with open(temp_zip, "wb") as f:
                    f.write(e.file.read())
                new_id = lib.import_voice(temp_zip)
                safe_notify(f"Imported voice with ID {new_id}", type="positive")
                dialog.close()
                refresh()
            except Exception as err:
                safe_notify(f"Import failed: {err}", type="negative")

        # Initial load
        refresh()
        search_input.on_value_change(lambda: refresh())

    return container
