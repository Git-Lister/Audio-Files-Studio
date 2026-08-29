"""
Audio‑Files Studio – main UI entry point.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from nicegui import app, ui

from bookforge.ui.components import (
    get_processor,
    init_notification_area,
    safe_notify,
    set_processor,
    update_progress_from_processor,
)
from bookforge.ui.views import finalize, home, prepare, projects, setup, synthesize


@ui.page("/")
async def main_page():
    ui.add_head_html("""
    <script>
    window.onbeforeunload = function(e) {
        if (document.getElementById("processing-indicator") !== null) {
            e.returnValue = "Processing is still running in the background. You can close the tab safely.";
            return e.returnValue;
        }
    };
    </script>
    """)

    init_notification_area()

    # ------------------------------------------------------------------
    # Create containers first
    # ------------------------------------------------------------------
    home_container = ui.column().classes("w-full")
    projects_container = ui.column().classes("w-full")
    pipeline_container = ui.column().classes("w-full")
    pipeline_step_label = ui.label("").classes("text-subtitle1 q-mb-md")

    # ------------------------------------------------------------------
    # Instantiate view functions
    # ------------------------------------------------------------------
    home_container = home.view(lambda: start_new_project(), lambda: show_view("projects"))
    projects_container = projects.view()
    setup_card = setup.view()
    prepare_card = prepare.view()
    synthesize_card = synthesize.view()
    finalize_card = finalize.view()

    step_cards = {
        "setup": setup_card,
        "prepare": prepare_card,
        "synthesize": synthesize_card,
        "finalize": finalize_card,
    }

    # Add step cards to pipeline container
    with pipeline_container:
        with ui.row().classes("w-full justify-end"):
            ui.button("← Back to Home", on_click=lambda: show_view("home")).props("flat")
        pipeline_step_label
        for card in step_cards.values():
            card.visible = False

    # ------------------------------------------------------------------
    # View switching helpers
    # ------------------------------------------------------------------
    def show_view(view: str):
        app.storage.general["current_view"] = view
        home_container.visible = view == "home"
        projects_container.visible = view == "projects"
        pipeline_container.visible = view == "pipeline"
        if view == "pipeline":
            proc = get_processor()
            if proc:
                if proc.is_complete():
                    show_pipeline_step("finalize")
                elif proc.book_text and proc.chapter_progress:
                    show_pipeline_step("synthesize")
                else:
                    show_pipeline_step("prepare")
            else:
                show_pipeline_step("setup")

    def show_pipeline_step(step: str):
        pipeline_step_label.set_text(f"Step: {step.title()}")
        for name, card in step_cards.items():
            card.visible = name == step

    def start_new_project():
        set_processor(None)
        setup.reset_form()
        show_view("pipeline")
        show_pipeline_step("setup")

    # ------------------------------------------------------------------
    # Link switch callbacks
    # ------------------------------------------------------------------
    setup_card.switch_to_prepare = lambda: show_pipeline_step("prepare")
    prepare_card.switch_to_synthesize = lambda: show_pipeline_step("synthesize")
    synthesize_card.switch_to_finalize = lambda: show_pipeline_step("finalize")
    finalize_card.switch_to_projects = lambda: show_view("projects")

    # ------------------------------------------------------------------
    # Resume logic
    # ------------------------------------------------------------------
    async def resume_project(project_name: str):
        from bookforge.incremental_processor import IncrementalProcessor
        from bookforge.tts.factory import get_backend

        progress_file = Path("out") / project_name / "processing_progress.json"
        if not progress_file.exists():
            safe_notify("No progress data found.", type="negative")
            return
        try:
            with progress_file.open("r") as f:
                data = json.load(f)
        except OSError as e:
            safe_notify(f"Failed to read progress file: {e}", type="negative")
            return

        backend_type = data.get("backend_name", "unknown")
        if backend_type == "unknown" or backend_type is None:
            if data.get("speaker_wav"):
                backend_type = "xtts"
            elif data.get("voice_model"):
                backend_type = "piper"
            else:
                safe_notify(
                    "Old project – cannot detect backend. Start a new project.", type="warning"
                )
                return

        voice_model_path = data.get("voice_model")
        speaker_wav_path = data.get("speaker_wav")
        voice_model = Path(voice_model_path) if voice_model_path else None
        speaker_wav = Path(speaker_wav_path) if speaker_wav_path else None

        try:
            tts_backend = await asyncio.to_thread(
                get_backend,
                backend_type=backend_type,
                voice_model=voice_model,
                speaker_wav=speaker_wav,
            )
        except Exception as e:  # noqa: BLE001
            safe_notify(f"Failed to recreate TTS backend: {e}", type="negative")
            return

        try:
            proc = IncrementalProcessor(
                input_file=Path(data["input_file"]),
                output_dir=Path("out") / project_name,
                backend=tts_backend,
                preset=data.get("preset", "calm_longform"),
                chapter_strategy=data.get("chapter_strategy", "auto"),
                chapter_min_confidence=float(data.get("chapter_min_confidence", 0.5)),
                normalize=data.get("normalize", False),
                target_lufs=float(data.get("target_lufs", -16.0)),
                voice_model=voice_model,
                speaker_wav=speaker_wav,
            )
            proc.backend_name = backend_type
            await asyncio.to_thread(proc.prepare_text)
            loaded = await asyncio.to_thread(proc.load_progress)
            if not loaded:
                safe_notify("No previous progress could be loaded.", type="warning")
                return
        except Exception as e:  # noqa: BLE001
            safe_notify(f"Failed to resume: {e}", type="negative")
            return

        set_processor(proc)
        update_progress_from_processor(proc)
        safe_notify(f"Resumed '{project_name}'", type="positive")
        show_view("pipeline")
        show_pipeline_step("synthesize")

    projects_container.on_resume = resume_project

    # ------------------------------------------------------------------
    # Initial view
    # ------------------------------------------------------------------
    active_proc = get_processor()
    if active_proc and active_proc.book_text:
        show_view("pipeline")
        if active_proc.is_complete():
            show_pipeline_step("finalize")
        else:
            show_pipeline_step("synthesize")
            update_progress_from_processor(active_proc)
    else:
        show_view("home")

    ui.markdown("---")
    ui.markdown("Audio‑Files Studio · MIT License · running locally")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=8501,
        title="Audio‑Files Studio",
        favicon="🎙️",
        reload=False,
        show=False,
    )
