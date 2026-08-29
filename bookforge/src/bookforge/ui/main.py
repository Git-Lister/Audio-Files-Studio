"""
Audio‑Files Studio – main UI entry point with sidebar navigation.
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
from bookforge.ui.views import finalize, home, prepare, projects, settings, setup, synthesize


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

    # Clear any stale processor state to avoid auto‑loading on fresh page
    set_processor(None)

    # ------------------------------------------------------------------
    # Sidebar and main content containers (created first)
    # ------------------------------------------------------------------
    with ui.header().classes("bg-primary text-white"):
        ui.label("🎙️ Audio‑Files Studio").classes("text-h5")
        project_badge = ui.label("").classes("text-caption")

    with ui.left_drawer().classes("bg-blue-grey-1"):
        with ui.column().classes("w-full p-4"):
            ui.label("Navigation").classes("text-h6 text-grey-8")
            ui.separator()
            ui.button("Home", on_click=lambda: navigate("home")).props("flat align=left")
            ui.button("Projects", on_click=lambda: navigate("projects")).props("flat align=left")
            ui.button("Settings", on_click=lambda: navigate("settings")).props("flat align=left")
            ui.separator()
            pipeline_label = ui.label("Project Pipeline").classes("text-h6 text-grey-8 mt-4")
            nav_setup = ui.button("1. Setup", on_click=lambda: navigate_pipeline("setup")).props(
                "flat align=left"
            )
            nav_prepare = ui.button(
                "2. Prepare", on_click=lambda: navigate_pipeline("prepare")
            ).props("flat align=left")
            nav_synthesize = ui.button(
                "3. Synthesize", on_click=lambda: navigate_pipeline("synthesize")
            ).props("flat align=left")
            nav_finalize = ui.button(
                "4. Finalize", on_click=lambda: navigate_pipeline("finalize")
            ).props("flat align=left")
            nav_review = ui.button("5. Review", on_click=lambda: navigate_pipeline("review")).props(
                "flat align=left"
            )
            # Initially hide pipeline items
            pipeline_label.visible = False
            nav_setup.visible = False
            nav_prepare.visible = False
            nav_synthesize.visible = False
            nav_finalize.visible = False
            nav_review.visible = False

    main_content = ui.column().classes("w-full p-4")

    # ------------------------------------------------------------------
    # Define navigation functions BEFORE creating view containers
    # ------------------------------------------------------------------
    def navigate(view: str):
        app.storage.general["current_view"] = view
        # Hide all containers
        for c in (
            home_container,
            projects_container,
            settings_container,
            setup_card,
            prepare_card,
            synthesize_card,
            finalize_card,
            review_card,
        ):
            c.visible = False
        if view == "home":
            home_container.visible = True
        elif view == "projects":
            projects_container.visible = True
        elif view == "settings":
            settings_container.visible = True
        pipeline_label.visible = False
        nav_setup.visible = False
        nav_prepare.visible = False
        nav_synthesize.visible = False
        nav_finalize.visible = False
        nav_review.visible = False
        update_project_badge()

    def navigate_pipeline(step: str):
        proc = get_processor()
        if proc is None:
            safe_notify("No active project. Start a new one or resume an existing.", type="warning")
            navigate("home")
            return
        app.storage.general["current_view"] = f"pipeline_{step}"
        for c in (
            home_container,
            projects_container,
            settings_container,
            setup_card,
            prepare_card,
            synthesize_card,
            finalize_card,
            review_card,
        ):
            c.visible = False
        if step == "setup":
            setup_card.visible = True
        elif step == "prepare":
            prepare_card.visible = True
        elif step == "synthesize":
            synthesize_card.visible = True
        elif step == "finalize":
            finalize_card.visible = True
        elif step == "review":
            review_card.visible = True
        pipeline_label.visible = True
        nav_setup.visible = True
        nav_prepare.visible = True
        nav_synthesize.visible = True
        nav_finalize.visible = True
        nav_review.visible = True
        update_project_badge()

    def update_project_badge():
        proc = get_processor()
        if proc:
            if proc.is_complete():
                project_badge.set_text(f"Project: {proc.output_dir.name} (Completed)")
            else:
                progress = proc.get_progress()
                project_badge.set_text(
                    f"Project: {proc.output_dir.name} – {progress.status_message}"
                )
        else:
            project_badge.set_text("")

    def start_new_project():
        set_processor(None)
        setup_card.reset_form()
        navigate_pipeline("setup")

    # ------------------------------------------------------------------
    # Create view containers inside main content (now functions exist)
    # ------------------------------------------------------------------
    with main_content:
        home_container = home.view(lambda: start_new_project(), lambda: navigate("projects"))
        projects_container = projects.view()
        settings_container = settings.view()
        setup_card = setup.view()
        prepare_card = prepare.view()
        synthesize_card = synthesize.view()
        finalize_card = finalize.view()
        review_card = ui.column()  # placeholder

        # Set all invisible initially
        home_container.visible = False
        projects_container.visible = False
        settings_container.visible = False
        setup_card.visible = False
        prepare_card.visible = False
        synthesize_card.visible = False
        finalize_card.visible = False
        review_card.visible = False

    # ------------------------------------------------------------------
    # Link switch callbacks (now containers exist)
    # ------------------------------------------------------------------
    setup_card.switch_to_prepare = lambda: navigate_pipeline("prepare")
    prepare_card.switch_to_synthesize = lambda: navigate_pipeline("synthesize")
    synthesize_card.switch_to_finalize = lambda: navigate_pipeline("finalize")
    finalize_card.switch_to_projects = lambda: navigate("projects")

    # ------------------------------------------------------------------
    # Resume project function (defined before assignment to projects container)
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
        navigate_pipeline("synthesize")

    projects_container.on_resume = resume_project

    # ------------------------------------------------------------------
    # Initial view – always start at home; no auto‑loading
    # ------------------------------------------------------------------
    navigate("home")

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
