# src/bookforge/ui/views/setup.py
"""Setup view – form for new project configuration and voice preview."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from nicegui import ui

from bookforge.ui.components import extract_upload_bytes, safe_notify, set_processor

PREVIEW_TEXT = "Hello! This is my voice. I hope it sounds clear and natural."


def view():
    """Build the Setup view and return the container with reset/switch methods."""
    # ----- local state (non‑UI) -----
    book_event: Any | None = None
    speaker_event: Any | None = None

    # ----- Helper functions (must be defined before UI elements that use them) -----
    def toggle_voice_options():
        """Show/hide the correct backend‑specific options."""
        if backend_radio.value == "piper":
            piper_group.visible = True
            xtts_group.visible = False
        else:
            piper_group.visible = False
            xtts_group.visible = True

    def on_book_upload(e):
        nonlocal book_event
        book_event = e
        name = (
            getattr(e.file, "name", "uploaded_book.txt")
            if hasattr(e, "file")
            else "uploaded_book.txt"
        )
        safe_notify(f"Book '{name}' selected", type="positive")

    def on_speaker_upload(e):
        nonlocal speaker_event
        speaker_event = e
        name = getattr(e.file, "name", "speaker.wav") if hasattr(e, "file") else "speaker.wav"
        speaker_label.set_text(f"✅ {name}")
        safe_notify(f"Speaker WAV '{name}' uploaded", type="positive")

    async def clone_settings(project_name: str):
        if not project_name:
            return
        meta_path = Path("out") / project_name / "meta.json"
        if not meta_path.exists():
            safe_notify("Project metadata not found.", type="negative")
            return
        try:
            with meta_path.open("r") as f:
                meta = json.load(f)
        except OSError as e:
            safe_notify(f"Failed to read metadata: {e}", type="negative")
            return

        # Populate form from metadata
        source_file = meta.get("source_file", "")
        book_name = Path(source_file).name if source_file else ""
        if book_name and (Path("books") / book_name).exists():
            book_select.value = book_name
        else:
            book_select.value = ""

        output_name.value = project_name
        backend_radio.value = meta.get("backend", "piper")
        toggle_voice_options()

        if meta.get("voice_model"):
            vm_path = Path(meta["voice_model"])
            vm_name = vm_path.name if vm_path.exists() else ""
            if vm_name and backend_radio.value == "piper":
                voice_model_select.value = vm_name

        preset_select.value = meta.get("preset", "calm_longform")
        chapter_strategy.value = meta.get("chapter_strategy", "auto")
        chapter_confidence.value = float(meta.get("chapter_min_confidence", 0.5))
        normalize_check.value = meta.get("normalize", False)
        if meta.get("target_lufs"):
            target_lufs.value = float(meta["target_lufs"])

        safe_notify(f"Cloned settings from '{project_name}'.", type="positive")

    async def setup_next():
        """Validate form, create processor, and switch to Prepare view."""
        setup_spinner.visible = True
        save_btn.disable()
        errors = []

        # ---- Gather book path ----
        book_path: Path | None = None
        if book_event is not None:
            try:
                book_bytes, book_filename = await extract_upload_bytes(book_event)
                book_path = Path("temp") / book_filename
                book_path.write_bytes(book_bytes)
            except Exception as e:
                errors.append(f"Failed to read uploaded book: {e}")
        elif book_select.value:
            book_path = Path("books") / book_select.value
        else:
            errors.append("Please select a book.")

        # ---- Validate output name ----
        if not output_name.value.strip():
            errors.append("Output project name is required.")

        # ---- Gather voice settings ----
        backend = backend_radio.value
        voice_model: Path | None = None
        speaker_wav: Path | None = None

        if backend == "piper":
            if not voice_model_select.value:
                errors.append("Piper voice model is required.")
            else:
                voice_model = Path("voices") / voice_model_select.value
                if not voice_model.exists():
                    errors.append(f"Voice model not found: {voice_model}")
        else:  # xtts
            if speaker_event is None:
                errors.append("XTTS requires a reference speaker WAV upload.")
            else:
                try:
                    speaker_bytes, speaker_filename = await extract_upload_bytes(speaker_event)
                    speaker_wav = Path("temp") / speaker_filename
                    speaker_wav.write_bytes(speaker_bytes)
                except Exception as e:
                    errors.append(f"Failed to read speaker WAV: {e}")

        # ---- Report errors ----
        if errors:
            for err in errors:
                safe_notify(err, type="negative")
            setup_spinner.visible = False
            save_btn.enable()
            return

        if book_path is None:
            safe_notify("Book path is missing.", type="negative")
            setup_spinner.visible = False
            save_btn.enable()
            return

        # ---- Create processor ----
        try:
            from bookforge.incremental_processor import IncrementalProcessor
            from bookforge.tts.factory import get_backend

            tts_backend = await asyncio.to_thread(
                get_backend,
                backend_type=backend,
                voice_model=voice_model,
                speaker_wav=speaker_wav,
            )

            proc = IncrementalProcessor(
                input_file=book_path,
                output_dir=Path("out") / output_name.value.strip(),
                backend=tts_backend,
                preset=preset_select.value,
                chapter_strategy=chapter_strategy.value,
                chapter_min_confidence=chapter_confidence.value,
                normalize=normalize_check.value,
                target_lufs=target_lufs.value,
                voice_model=voice_model,
                speaker_wav=speaker_wav,
            )
            proc.backend_name = backend
            set_processor(proc)
            safe_notify("Configuration saved!", type="positive")
            # Switch to Prepare view (callback set by main.py)
            if hasattr(container, "switch_to_prepare") and container.switch_to_prepare:
                container.switch_to_prepare()
        except Exception as e:
            safe_notify(f"Failed to create processor: {e}", type="negative")
        finally:
            setup_spinner.visible = False
            save_btn.enable()

    async def voice_preview():
        """Generate a short preview using the current TTS settings."""
        preview_spinner.visible = True
        preview_audio.classes("hidden")
        backend = backend_radio.value
        voice_model: Path | None = None
        speaker_wav: Path | None = None

        try:
            if backend == "piper":
                if not voice_model_select.value:
                    safe_notify("Select a Piper voice model first.", type="warning")
                    return
                voice_model = Path("voices") / voice_model_select.value
                if not voice_model.exists():
                    safe_notify(f"Voice model not found: {voice_model}", type="negative")
                    return
            else:  # xtts
                if speaker_event is None:
                    safe_notify("Upload a reference speaker WAV first.", type="warning")
                    return
                try:
                    speaker_bytes, speaker_filename = await extract_upload_bytes(speaker_event)
                    speaker_wav = Path("temp") / speaker_filename
                    speaker_wav.write_bytes(speaker_bytes)
                except Exception as e:
                    safe_notify(f"Failed to read speaker WAV: {e}", type="negative")
                    return

            from bookforge.config import PresetConfig
            from bookforge.process.chunker import Chunk
            from bookforge.tts.factory import get_backend

            config = PresetConfig.load(preset_select.value)
            preview_chunk = Chunk(
                id=9999,
                chapter_index=0,
                relative_index=0,
                text=PREVIEW_TEXT,
                estimated_seconds=5.0,
            )

            tts_backend = await asyncio.to_thread(
                get_backend,
                backend_type=backend,
                voice_model=voice_model,
                speaker_wav=speaker_wav,
            )

            tmp_wav = Path("temp") / f"preview_{backend}.wav"
            await asyncio.to_thread(tts_backend.synthesize_chunk, preview_chunk, config, tmp_wav)

            if tmp_wav.exists():
                preview_audio.set_source(str(tmp_wav))
                preview_audio.classes(remove="hidden")
                safe_notify("Preview ready!", type="positive")
            else:
                safe_notify("Preview generation failed.", type="negative")
        except Exception as e:
            safe_notify(f"Voice preview error: {e}", type="negative")
        finally:
            preview_spinner.visible = False

    def reset_form():
        """Reset all form fields and clear uploaded file state."""
        nonlocal book_event, speaker_event
        book_event = None
        speaker_event = None
        book_select.value = ""
        output_name.value = "my-audiobook"
        backend_radio.value = "xtts"
        toggle_voice_options()
        preset_select.value = "calm_longform"
        chapter_strategy.value = "auto"
        chapter_confidence.value = 0.5
        normalize_check.value = False
        target_lufs.value = -16.0
        speaker_label.set_text("No speaker file selected")
        clone_select.value = ""
        preview_audio.classes("hidden")
        preview_audio.set_source("")

    # ----- Build the UI (now all functions are defined) -----
    container = ui.column().classes("w-full")

    with container:
        ui.label("1. Setup").classes("text-h5 q-mb-md")
        ui.markdown("Choose your input, TTS backend, and voice settings.")

        # ---- Clone settings ----
        with ui.row().classes("items-center gap-2 q-mb-md"):
            ui.label("Clone settings from").classes("text-caption")
            clone_select = ui.select(
                options=[""],
                value="",
                on_change=lambda e: asyncio.create_task(clone_settings(e.value)),
            ).classes("w-64")
            ui.tooltip("Copy configuration from a previous project")

        # ---- Two‑column layout ----
        with ui.row().classes("w-full gap-8"):
            # Left column: Source
            with ui.column().classes("col-12 col-md-6"):
                ui.label("Source").classes("font-bold")

                book_select = ui.select(
                    label="Book from books/",
                    options=[""]
                    + sorted([p.name for p in Path("books").glob("*.txt") if p.is_file()]),
                    value="",
                ).classes("w-full")
                ui.tooltip("Select a .txt file from the books folder")

                ui.upload(
                    label="Or upload a .txt file",
                    on_upload=on_book_upload,  # now defined
                ).classes("w-full")

                output_name = ui.input(
                    label="Output project name",
                    value="my-audiobook",
                ).classes("w-full")
                ui.tooltip("Folder name under out/ where your audiobook will be stored")

            # Right column: Voice
            with ui.column().classes("col-12 col-md-6"):
                ui.label("Voice").classes("font-bold")

                backend_radio = ui.radio(
                    ["piper", "xtts"],
                    value="xtts",
                    on_change=toggle_voice_options,
                ).props("inline")
                ui.tooltip("XTTS offers high‑quality voice cloning; Piper is fast CPU‑based")

                # ---- Dynamic voice options container ----
                voice_options = ui.column().classes("w-full")

                # Piper‑specific widgets
                with voice_options:
                    piper_group = ui.column().classes("w-full")
                    voice_model_select = ui.select(
                        label="Piper voice model",
                        options=[""]
                        + sorted([p.name for p in Path("voices").glob("*.onnx") if p.is_file()]),
                        value="",
                    ).classes("w-full")

                    # XTTS‑specific widgets
                    xtts_group = ui.column().classes("w-full")
                    speaker_label = ui.label("No speaker file selected").classes(
                        "text-caption text-grey"
                    )
                    ui.upload(
                        label="Reference speaker WAV",
                        on_upload=on_speaker_upload,  # now defined
                        auto_upload=True,
                    ).classes("w-full")

                # ---- Static voice settings ----
                preset_select = ui.select(
                    label="Preset",
                    options=["calm_longform", "calm_longform_v2"],
                    value="calm_longform",
                ).classes("w-full")
                ui.tooltip("Voice pacing and chunk size preset")

                chapter_strategy = ui.select(
                    label="Chapter detection",
                    options=["auto", "markdown", "structured", "heuristic", "paragraph", "none"],
                    value="auto",
                ).classes("w-full")
                ui.tooltip("How to split the book into chapters")

                chapter_confidence = ui.slider(min=0.0, max=1.0, step=0.05, value=0.5).classes(
                    "w-full"
                )
                ui.label().bind_text_from(
                    chapter_confidence,
                    "value",
                    backward=lambda v: f"Confidence: {v:.2f}",
                )

                normalize_check = ui.checkbox("Normalize final book", value=False)
                target_lufs = ui.number(
                    label="Target LUFS",
                    value=-16.0,
                    step=0.5,
                    format="%.1f",
                ).bind_visibility_from(normalize_check, "value")

        # ---- Action buttons ----
        with ui.row().classes("items-center gap-4"):
            save_btn = ui.button("Save & Continue", on_click=setup_next).props(
                "unelevated color=primary"
            )
            setup_spinner = ui.spinner(size="md").props("color=primary")
            setup_spinner.visible = False

        # ---- Voice preview ----
        with ui.row().classes("items-center gap-4"):
            ui.button("Test Voice", on_click=voice_preview).props("flat color=secondary")
            preview_spinner = ui.spinner(size="sm").props("color=secondary")
            preview_spinner.visible = False
            preview_audio = ui.audio("").classes("hidden q-mt-md")

    # Attach reset and switch callback to container
    container.reset_form = reset_form
    container.switch_to_prepare = None  # set by main.py

    # Initial visibility
    toggle_voice_options()

    return container
