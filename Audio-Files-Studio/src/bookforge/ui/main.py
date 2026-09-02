# src/bookforge/ui/main.py
"""Audio‑Files Studio – main UI with single content container."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from nicegui import app, ui

from bookforge.ui import state
from bookforge.ui.components import (
    init_notification_area,
    safe_notify,
    update_notification_panel,
    update_progress_from_processor,
)
from bookforge.ui.views import home, pipeline, projects, settings, vocalizer, voice_box, wizard

os.environ["TRANSFORMERS_VERBOSITY"] = "error"


@ui.page("/")
async def main_page():
    ui.add_head_html("""
    <style>
        body { font-family: 'Inter', sans-serif; }
        .bg-primary { background-color: #1a1a2e !important; }
        .bg-secondary { background-color: #0f3460 !important; }
        .bg-accent { background-color: #c9a959 !important; }
        .text-primary { color: #1a1a2e !important; }
        .text-secondary { color: #0f3460 !important; }
        .text-accent { color: #c9a959 !important; }
        .text-gold { color: #c9a959 !important; }
        .border-gold { border: 1px solid #c9a959 !important; }
        .shadow-gold { box-shadow: 0 4px 12px rgba(201, 169, 89, 0.2) !important; }
        .btn-gold { background-color: #c9a959 !important; color: #1a1a2e !important; }
        .btn-gold:hover { background-color: #b8963e !important; }
        .q-card { border-radius: 12px !important; box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important; }
        .dark .text-grey-8 { color: #c0c0c0 !important; }
        .dark .text-grey-6 { color: #a0a0a0 !important; }
    </style>
    """)

    init_notification_area()

    # Init state
    state.set_processor(None)
    state.set_current_view("home")
    state.set_pipeline_step(None)

    # ---- Dark mode management ----
    def apply_dark_mode(enabled: bool):
        """Apply dark mode to all UI elements."""
        state.set_dark_mode(enabled)
        ui.dark_mode(enabled)
        # Update sidebar background
        if enabled:
            drawer.classes(remove="bg-blue-grey-1", add="bg-grey-9")
            dark_btn.icon = "light_mode"
        else:
            drawer.classes(remove="bg-grey-9", add="bg-blue-grey-1")
            dark_btn.icon = "dark_mode"
        # Update notification panel text colors
        update_notification_panel()
        # Update settings toggle if it exists
        if hasattr(state, "_settings_dark_toggle") and state._settings_dark_toggle is not None:
            state._settings_dark_toggle.value = enabled

    def toggle_dark_mode():
        new_mode = not state.get_dark_mode()
        apply_dark_mode(new_mode)

    # Initial dark mode
    dark_mode = state.get_dark_mode()
    ui.dark_mode(dark_mode)

    # ---- Header ----
    with ui.header().classes("bg-primary text-white"):
        ui.button(icon="menu", on_click=lambda: drawer.toggle()).props("flat color=white")
        ui.label("📚 Audio‑Files Studio").classes("text-h5")
        project_badge = ui.label("").classes("text-caption text-gold q-ml-auto")
        dark_btn = ui.button(
            icon="dark_mode" if not dark_mode else "light_mode", on_click=toggle_dark_mode
        ).props("flat color=white")

    # ---- Sidebar (dynamic background) ----
    drawer = ui.left_drawer().classes("bg-blue-grey-1")
    if dark_mode:
        drawer.classes(remove="bg-blue-grey-1", add="bg-grey-9")
    with drawer:
        with ui.column().classes("w-full p-4"):
            ui.label("Navigation").classes("text-h6 text-grey-8")
            ui.separator()
            ui.button("Home", icon="home", on_click=lambda: navigate("home")).props(
                "flat align=left"
            )
            ui.button("New Project", icon="add", on_click=lambda: navigate("wizard")).props(
                "flat align=left color=primary"
            )
            ui.button("Projects", icon="folder", on_click=lambda: navigate("projects")).props(
                "flat align=left"
            )
            ui.button("Voice Box (Gallery)", icon="library_books", on_click=lambda: navigate("voice_box")).props(
                "flat align=left"
            )

            ui.button("Vocalizer (Creator)", icon="edit", on_click=lambda: navigate("vocalizer")).props(
                "flat align=left"
            )

            ui.button("Settings", icon="settings", on_click=lambda: navigate("settings")).props(
                "flat align=left"
            )
            ui.separator()

            pipeline_label = ui.label("Pipeline").classes("text-h6 text-grey-8 mt-4")
            nav_prepare = ui.button(
                "1. Prepare", on_click=lambda: navigate_pipeline("prepare")
            ).props("flat align=left")
            nav_synthesize = ui.button(
                "2. Synthesize", on_click=lambda: navigate_pipeline("synthesize")
            ).props("flat align=left")
            nav_finalize = ui.button(
                "3. Finalize", on_click=lambda: navigate_pipeline("finalize")
            ).props("flat align=left")

            for item in (pipeline_label, nav_prepare, nav_synthesize, nav_finalize):
                item.bind_visibility_from(app.storage.general, "project_active")

            app.storage.general["project_active"] = False

    # ---- Main content ----
    notification_panel = ui.column().classes("w-full q-pa-md")
    import bookforge.ui.components as comp

    comp._notification_panel = notification_panel
    with notification_panel:
        ui.label("📢 Notifications").classes("text-subtitle1")

    content = ui.column().classes("w-full p-4")

    # ---- Navigation functions ----
    def navigate(view_name: str):
        content.clear()
        with content:
            if view_name == "home":
                home.view(on_new_project=lambda: navigate("wizard"))
            elif view_name == "projects":
                projects.view()
            elif view_name == "voice_box":
                voice_box.view(switch_to_vocalizer_callback=lambda: navigate("vocalizer"))
            elif view_name == "vocalizer":
                vocalizer.view(switch_to_gallery_callback=lambda: navigate("voice_box"))
            elif view_name == "settings":
                settings.view(on_dark_toggle=apply_dark_mode)
            elif view_name == "wizard":
                wizard.view(on_switch_to_pipeline=navigate_pipeline)
            elif view_name == "pipeline":
                try:
                    pipeline.view(on_switch_to_projects=lambda: navigate("projects"))
                except Exception as e:
                    safe_notify(f"Pipeline error: {e}", type="negative")
                    import traceback

                    traceback.print_exc()
                    ui.label(f"Pipeline failed to load. See notifications above.").classes(
                        "text-negative"
                    )
            else:
                ui.label("Unknown view")
        state.set_current_view(view_name)
        update_badge()

    def navigate_pipeline(step: str):
        proc = state.get_processor()
        if proc is None:
            safe_notify("No active project. Start a new one.", type="warning")
            navigate("home")
            return
        state.set_pipeline_step(step)
        app.storage.general["project_active"] = True
        navigate("pipeline")

    def update_badge():
        proc = state.get_processor()
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

    def clear_notifications():
        comp._notifications.clear()
        update_notification_panel()

    # ---- Resume project (for projects view) ----
    async def resume_project(project_name: str):
        from bookforge.incremental_processor import IncrementalProcessor
        from bookforge.tts.factory import get_backend

        progress_file = Path("out") / project_name / "processing_progress.json"
        if not progress_file.exists():
            safe_notify("No progress data.", type="negative")
            return
        try:
            with progress_file.open("r") as f:
                data = json.load(f)
        except OSError as e:
            safe_notify(f"Failed to read progress: {e}", type="negative")
            return

        backend_type = data.get("backend_name", "unknown")
        if backend_type == "unknown":
            if data.get("speaker_wav"):
                backend_type = "xtts"
            elif data.get("voice_model"):
                backend_type = "piper"
            else:
                safe_notify("Cannot detect backend.", type="warning")
                return

        voice_model = Path(data["voice_model"]) if data.get("voice_model") else None
        speaker_wav = Path(data["speaker_wav"]) if data.get("speaker_wav") else None
        backend_params = data.get("backend_params", {})

        try:
            tts_backend = await asyncio.to_thread(
                get_backend,
                backend_type=backend_type,
                voice_model=voice_model,
                speaker_wav=speaker_wav,
                **backend_params,
            )
        except Exception as e:
            safe_notify(f"Failed to recreate backend: {e}", type="negative")
            return

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
            skip_failed=data.get("skip_failed", False),
            backend_params=backend_params,
        )
        proc.backend_name = backend_type
        await asyncio.to_thread(proc.prepare_text)
        loaded = await asyncio.to_thread(proc.load_progress)
        if not loaded:
            safe_notify("No progress could be loaded.", type="warning")
            return
        state.set_processor(proc)
        app.storage.general["project_active"] = True
        update_progress_from_processor(proc)
        safe_notify(f"Resumed '{project_name}'", type="positive")
        navigate_pipeline("synthesize")

    # ---- Store resume callback ----
    state.set_resume_callback(resume_project)

    # ---- Initial view ----
    navigate("home")

    ui.markdown("---")
    ui.markdown("Audio‑Files Studio · MIT License · running locally")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=8501,
        title="Audio‑Files Studio",
        favicon="📚",
        reload=False,
        show=False,
    )
