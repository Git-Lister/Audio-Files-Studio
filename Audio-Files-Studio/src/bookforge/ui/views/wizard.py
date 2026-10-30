# src/bookforge/ui/views/wizard.py
"""New Project – single form setup for book, voice, preset, and project name."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from nicegui import ui

from bookforge.config import PresetConfig
from bookforge.ui import voice_library as lib
from bookforge.ui.components import extract_upload_bytes, safe_notify, set_processor


def sanitise_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9 _.-]", "_", name)


def view(on_switch_to_pipeline=None):
    container = ui.column().classes("w-full max-w-3xl mx-auto")

    # State
    state = {
        "book_path": None,
        "book_event": None,
        "voice_id": None,
        "speaker_wav": None,
        "backend": "xtts",
    }

    def check_collision() -> str | None:
        name = project_name_input.value.strip() if project_name_input else ""
        if not name:
            return "Project name is required."
        sanitised = sanitise_filename(name)
        if (Path("out") / sanitised).exists():
            return f"A project named '{sanitised}' already exists."
        return None

    def update_create_button():
        err = check_collision()
        if err:
            create_btn.disable()
            if "already exists" in err:
                collision_label.set_text(f"⚠️ {err} Choose a different name.")
                collision_label.visible = True
            else:
                collision_label.visible = False
        else:
            create_btn.enable()
            collision_label.visible = False

    async def handle_book_upload(e):
        state["book_event"] = e
        name = getattr(e.file, "name", "uploaded_book.txt")
        book_status.set_text(f"Uploaded: {name}")
        safe_notify(f"Book '{name}' uploaded", type="positive")

    def on_book_select(e):
        value = e.value
        if value:
            state["book_path"] = Path("books") / value
            state["book_event"] = None
            book_status.set_text(f"Selected: {value}")
        else:
            state["book_path"] = None
            book_status.set_text("No book selected")

    def on_voice_select(e):
        voice_id = e.value
        state["voice_id"] = voice_id or None
        if not voice_id:
            voice_status.set_text("No voice selected. Using default/uploaded reference.")
            state["speaker_wav"] = None
            return

        voice = lib.get_voice(voice_id)
        if voice:
            ref_path = Path(lib.get_voice_dir(voice_id)) / "reference.wav"
            if ref_path.exists():
                state["speaker_wav"] = ref_path
                voice_status.set_text(f"Using voice: {voice['name']}")
            else:
                state["speaker_wav"] = None
                voice_status.set_text(f"⚠️ {voice['name']} is missing its reference WAV.")

    async def create_project():
        err = check_collision()
        if err:
            safe_notify(err, type="negative")
            return

        name = project_name_input.value.strip()
        sanitised = sanitise_filename(name)
        output_dir = Path("out") / sanitised

        if not state["book_path"] and not state["book_event"]:
            safe_notify("Please select or upload a book.", type="negative")
            return

        if state["backend"] == "xtts" and state["speaker_wav"] is None:
            safe_notify("Please select a voice from the gallery or upload a reference.", type="negative")
            return

        create_btn.disable()
        create_btn.set_text("Creating...")

        try:
            # Save book if uploaded
            book_path = state["book_path"]
            if book_path is None and state["book_event"] is not None:
                book_bytes, book_filename = await extract_upload_bytes(state["book_event"])
                book_path = Path("temp") / book_filename
                book_path.write_bytes(book_bytes)

            # Load preset
            preset_name = preset_select.value
            config = PresetConfig.load(preset_name)

            # Build VoiceProfile and init backend
            from bookforge.tts.factory import get_backend
            from bookforge.voice_profile import VoiceProfile
            voice = VoiceProfile(
                backend_type=state["backend"],
                reference_wav=state["speaker_wav"],
                temperature=config.temperature,
                length_penalty=config.length_penalty,
                repetition_penalty=config.repetition_penalty,
                language="en",
            )
            tts_backend = await asyncio.to_thread(get_backend, voice)

            # Init Processor
            from bookforge.incremental_processor import IncrementalProcessor
            proc = IncrementalProcessor(
                input_file=book_path,
                output_dir=output_dir,
                backend=tts_backend,
                voice=voice,
                preset=preset_name,
                chapter_strategy="auto",
                chapter_min_confidence=0.5,
                normalize=False,
            )
            proc.backend_name = state["backend"]
            set_processor(proc)

            safe_notify(f"Project '{sanitised}' created!", type="positive")
            if on_switch_to_pipeline:
                on_switch_to_pipeline("prepare")

        except Exception as ex:
            safe_notify(f"Creation failed: {ex}", type="negative")
            create_btn.enable()
            create_btn.set_text("Create Project")

    with container:
        ui.label("📖 New Project").classes("text-h4 q-mb-md")

        # --- Book section ---
        with ui.card().classes("w-full q-mb-md"):
            ui.label("1. Book").classes("text-h6")
            book_options = [""] + sorted([p.name for p in Path("books").glob("*.txt") if p.is_file()])
            book_select = ui.select(label="Select from books/", options=book_options, value="", on_change=on_book_select).classes("w-full")
            book_status = ui.label("No book selected").classes("text-caption text-grey")
            ui.upload(label="Or upload a new .txt file", on_upload=handle_book_upload, auto_upload=True).classes("w-full")

        # --- Voice section ---
        with ui.card().classes("w-full q-mb-md"):
            ui.label("2. Voice").classes("text-h6")
            voices = lib.list_voices(system=False)
            voice_options = {"": "— Upload custom reference below —"}
            for v in voices:
                voice_options[v["id"]] = v["name"]

            voice_select = ui.select(label="Select from Voice Box", options=voice_options, value="", on_change=on_voice_select).classes("w-full")
            voice_status = ui.label("No voice selected").classes("text-caption text-grey")

            async def handle_voice_upload(e):
                temp_dir = Path("temp")
                ref_path = temp_dir / f"ref_{re.sub(r'[^a-zA-Z0-9.]', '_', e.file.name)}"
                content = await e.file.read()
                with open(ref_path, "wb") as f:
                    f.write(content)
                state["speaker_wav"] = ref_path
                state["voice_id"] = None
                voice_select.value = ""  # Deselect dropdown
                voice_status.set_text(f"Uploaded: {e.file.name}")

            ui.upload(label="Or upload a custom reference WAV", on_upload=handle_voice_upload, auto_upload=True).classes("w-full")

        # --- Settings section ---
        with ui.card().classes("w-full q-mb-md"):
            ui.label("3. Settings").classes("text-h6")
            presets = PresetConfig.list_presets()
            preset_options = presets["system"] + presets["user"]
            preset_select = ui.select(label="Preset", options=preset_options, value="calm_longform").classes("w-full")

            project_name_input = ui.input(label="Project Name", value="", on_change=lambda: update_create_button()).classes("w-full q-mt-sm")
            collision_label = ui.label("").classes("text-negative text-caption")
            collision_label.visible = False

        # --- Actions ---
        with ui.row().classes("w-full justify-end q-mt-md gap-4"):
            create_btn = ui.button("Create Project", on_click=create_project).props("color=primary size=lg")
            create_btn.disable()

            ui.button("Cancel", on_click=lambda: on_switch_to_pipeline(None) if on_switch_to_pipeline else None).props("flat")

    return container
