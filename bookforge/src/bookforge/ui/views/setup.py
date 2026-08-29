"""
Setup view – form for new project configuration.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from nicegui import ui

from bookforge.ui.components import extract_upload_bytes, safe_notify, set_processor


def view():
    container = ui.column().classes("w-full")
    # Define local state variables at the top for nonlocal usage
    book_event: Any | None = None
    speaker_event: Any | None = None

    with container:
        ui.label("1. Setup").classes("text-h5 q-mb-md")
        ui.markdown("Choose your input, TTS backend, and voice settings.")

        # Clone settings from existing project
        with ui.row().classes("items-center gap-2 q-mb-md"):
            ui.label("Clone settings from").classes("text-caption")
            clone_select = ui.select(
                options=[""],
                value="",
                on_change=lambda e: clone_settings(e.value),
            ).classes("w-64")
            ui.tooltip("Copy configuration from a previous project")

        with ui.row().classes("w-full gap-8"):
            with ui.column().classes("col-12 col-md-6"):
                ui.label("📖 Source").classes("font-bold")
                book_select = ui.select(
                    label="Book from books/",
                    options=[""]
                    + sorted([p.name for p in Path("books").glob("*.txt") if p.is_file()]),
                    value="",
                ).classes("w-full")
                ui.tooltip("Select a .txt file from the books folder")
                ui.upload(
                    label="Or upload a .txt file",
                    on_upload=lambda e: on_book_upload(e),
                ).classes("w-full")
                output_name = ui.input(label="Output project name", value="my-audiobook").classes(
                    "w-full"
                )
                ui.tooltip("Folder name under out/ where your audiobook will be stored")

            with ui.column().classes("col-12 col-md-6"):
                ui.label("🎤 Voice").classes("font-bold")
                backend_radio = ui.radio(
                    ["piper", "xtts"], value="xtts", on_change=lambda: build_voice_widgets()
                ).props("inline")
                ui.tooltip("XTTS offers high‑quality voice cloning; Piper is fast CPU‑based")
                voice_container = ui.column().classes("w-full")
                voice_model_select: ui.select | None = None
                speaker_label = ui.label("No speaker file selected").classes(
                    "text-caption text-grey"
                )

                def build_voice_widgets():
                    nonlocal voice_model_select
                    voice_container.clear()
                    if backend_radio.value == "piper":
                        voice_model_select = ui.select(
                            label="Piper voice model",
                            options=[""]
                            + sorted(
                                [p.name for p in Path("voices").glob("*.onnx") if p.is_file()]
                            ),
                            value="",
                        ).classes("w-full")
                        ui.tooltip("Choose an ONNX voice model from voices/")
                    else:
                        ui.upload(
                            label="Reference speaker WAV",
                            on_upload=lambda e: on_speaker_upload(e),
                            auto_upload=True,
                        ).classes("w-full")
                        ui.tooltip("Upload a clear WAV sample – processed immediately")
                        voice_model_select = None

                build_voice_widgets()

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
                    chapter_confidence, "value", backward=lambda v: f"Confidence: {v:.2f}"
                )
                normalize_check = ui.checkbox("Normalize final book", value=False)
                target_lufs = ui.number(
                    label="Target LUFS", value=-16.0, step=0.5, format="%.1f"
                ).bind_visibility_from(normalize_check, "value")

        # Save button with spinner
        with ui.row().classes("items-center gap-4"):
            save_btn = ui.button("Save & Continue", on_click=lambda: setup_next()).props(
                "unelevated color=primary"
            )
            setup_spinner = ui.spinner(size="md").props("color=primary")
            setup_spinner.visible = False

        # Voice preview button (placeholder)
        preview_btn = ui.button("Test Voice", on_click=lambda: voice_preview()).props(
            "flat color=secondary"
        )
        preview_spinner = ui.spinner(size="sm").props("color=secondary")
        preview_spinner.visible = False

    # ------------------------------------------------------------------
    # Helper functions
    # ------------------------------------------------------------------
    def reset_form():
        book_select.value = ""
        output_name.value = "my-audiobook"
        backend_radio.value = "xtts"
        build_voice_widgets()
        preset_select.value = "calm_longform"
        chapter_strategy.value = "auto"
        chapter_confidence.value = 0.5
        normalize_check.value = False
        target_lufs.value = -16.0
        speaker_label.set_text("No speaker file selected")
        clone_select.value = ""

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
        source_file = meta.get("source_file", "")
        book_name = Path(source_file).name if source_file else ""
        if book_name and (Path("books") / book_name).exists():
            book_select.value = book_name
        else:
            book_select.value = ""
        output_name.value = project_name
        backend_radio.value = meta.get("backend", "piper")
        build_voice_widgets()
        if meta.get("voice_model"):
            vm_path = Path(meta["voice_model"])
            vm_name = vm_path.name if vm_path.exists() else ""
            if vm_name and backend_radio.value == "piper" and voice_model_select:
                voice_model_select.value = vm_name
        preset_select.value = meta.get("preset", "calm_longform")
        chapter_strategy.value = meta.get("chapter_strategy", "auto")
        chapter_confidence.value = float(meta.get("chapter_min_confidence", 0.5))
        normalize_check.value = meta.get("normalize", False)
        if meta.get("target_lufs"):
            target_lufs.value = float(meta["target_lufs"])
        safe_notify(f"Cloned settings from '{project_name}'.")

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

    async def setup_next():
        nonlocal book_event, speaker_event
        setup_spinner.visible = True
        save_btn.disable()
        errors = []
        book_path: Path | None = None
        if book_event is not None:
            try:
                book_bytes, book_filename = await extract_upload_bytes(book_event)
                book_path = Path("temp") / book_filename
                book_path.write_bytes(book_bytes)
            except Exception as e:  # noqa: BLE001
                errors.append(f"Failed to read uploaded book: {e}")
        elif book_select.value:
            book_path = Path("books") / book_select.value
        else:
            errors.append("Please select a book.")
        if not output_name.value.strip():
            errors.append("Output project name is required.")
        backend = backend_radio.value
        voice_model: Path | None = None
        speaker_wav: Path | None = None
        if backend == "piper":
            if not voice_model_select or not voice_model_select.value:
                errors.append("Piper voice model is required.")
            else:
                voice_model = Path("voices") / voice_model_select.value
                if not voice_model.exists():
                    errors.append(f"Voice model not found: {voice_model}")
        else:
            if speaker_event is None:
                errors.append("XTTS requires a reference speaker WAV upload.")
            else:
                try:
                    speaker_bytes, speaker_filename = await extract_upload_bytes(speaker_event)
                    speaker_wav = Path("temp") / speaker_filename
                    speaker_wav.write_bytes(speaker_bytes)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"Failed to read speaker WAV: {e}")
        if errors:
            for err in errors:
                safe_notify(err, type="negative")
            setup_spinner.visible = False
            save_btn.enable()
            return
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
                input_file=book_path,  # Now assured not None
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
            container.switch_to_prepare()
        except Exception as e:  # noqa: BLE001
            safe_notify(f"Failed to create processor: {e}", type="negative")
        finally:
            setup_spinner.visible = False
            save_btn.enable()

    async def voice_preview():
        preview_spinner.visible = True
        safe_notify("Voice preview coming soon!", type="warning")
        preview_spinner.visible = False

    # Expose functions needed by main
    container.reset_form = reset_form
    container.switch_to_prepare = None  # will be set by main
    return container
