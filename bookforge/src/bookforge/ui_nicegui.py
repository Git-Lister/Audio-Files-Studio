"""
Audio‑Files Studio – polished UX with instant uploads, spinners, and XTTS default
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from nicegui import app, ui

from bookforge.incremental_processor import AbortException, IncrementalProcessor
from bookforge.project import BookProject
from bookforge.tts.factory import get_backend

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BOOKS_DIR = Path("books")
VOICES_DIR = Path("voices")
OUT_DIR = Path("out")
TMP_DIR = Path("temp")
TMP_DIR.mkdir(exist_ok=True)
APP_TITLE = "🎙️ Audio‑Files Studio"


# ---------------------------------------------------------------------------
# Shared state (survives page reloads)
# ---------------------------------------------------------------------------
def get_processor() -> Optional[IncrementalProcessor]:
    return app.storage.general.get("processor")


def set_processor(p: Optional[IncrementalProcessor]):
    app.storage.general["processor"] = p


def get_progress_dict() -> dict:
    return app.storage.general.get(
        "progress",
        {
            "overall_progress": 0.0,
            "chapter_progress": 0.0,
            "status_message": "Idle",
            "estimated_time_remaining": "",
            "chapter_statuses_html": "",
            "active": False,
        },
    )


def set_progress_dict(d: dict):
    app.storage.general["progress"] = d


async def run_in_thread(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


def update_progress_from_processor(proc: IncrementalProcessor):
    progress = proc.get_progress()
    html_parts = ['<div style="display:flex; flex-wrap:wrap; gap:8px;">']
    for ch in proc.chapter_statuses:
        badge = "⚪"
        if ch["error"]:
            badge = "🔴"
        elif ch["processed"]:
            badge = "🟢"
        else:
            badge = "🔵" if ch["chunks_done"] > 0 else "⚪"
        status_text = f"{badge} Ch{ch['index']}"
        if ch["error"]:
            status_text += " ❌"
        html_parts.append(
            f'<span style="padding:4px 8px; border:1px solid #ccc; border-radius:4px; font-size:0.85rem;">{status_text}</span>'
        )
    html_parts.append("</div>")
    set_progress_dict(
        {
            "overall_progress": progress.overall_progress,
            "chapter_progress": progress.chapter_progress,
            "status_message": f"{progress.status_message} (ETA: {progress.estimated_time_remaining})",
            "estimated_time_remaining": progress.estimated_time_remaining,
            "chapter_statuses_html": "".join(html_parts),
        }
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def list_books() -> list[str]:
    return sorted([p.name for p in BOOKS_DIR.glob("*.txt") if p.is_file()])


def list_voices() -> list[str]:
    return sorted([p.name for p in VOICES_DIR.glob("*.onnx") if p.is_file()])


def list_projects() -> list[str]:
    completed = sorted(
        [p.name for p in OUT_DIR.iterdir() if p.is_dir() and (p / "meta.json").exists()]
    )
    incomplete = sorted(
        [
            p.name
            for p in OUT_DIR.iterdir()
            if p.is_dir()
            and (p / "processing_progress.json").exists()
            and not (p / "meta.json").exists()
        ]
    )
    return completed + incomplete


async def extract_upload_bytes(e) -> tuple[bytes, str]:
    source = None
    if hasattr(e, "file") and e.file is not None:
        source = e.file
    elif hasattr(e, "files") and e.files:
        source = e.files[0]
    if source is None:
        raise AttributeError("Upload event has no file data.")
    if hasattr(source, "data") and source.data is not None:
        data = source.data
        if isinstance(data, bytes):
            return data, getattr(source, "name", "uploaded_file")
        if asyncio.iscoroutine(data):
            result = await data
            if isinstance(result, bytes):
                return result, getattr(source, "name", "uploaded_file")
            if hasattr(result, "read"):
                return result.read(), getattr(source, "name", "uploaded_file")
    if hasattr(source, "content") and source.content is not None:
        return source.content.read(), getattr(source, "name", "uploaded_file")
    if hasattr(source, "read"):
        val = source.read()
        if asyncio.iscoroutine(val):
            val = await val
        if isinstance(val, bytes):
            return val, getattr(source, "name", "uploaded_file")
    raise AttributeError(f"Cannot extract bytes from {type(source).__name__}")


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------
@ui.page("/")
async def main_page():
    # ── Local state ──
    processor = None
    book_event = None
    speaker_event = None

    # ── Before‑unload warning ──
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

    # ── Notification area ──
    with ui.column().classes("w-full") as notif_area:
        pass

    def safe_notify(msg: str, type: str = "positive"):
        with notif_area:
            ui.notify(msg, type=type, timeout=5)

    # ── Views ──
    with ui.column().classes("w-full") as main_container:
        # HOME
        with ui.column().classes("w-full") as home_card:
            with ui.card().classes("w-full q-pa-xl text-center"):
                ui.label(APP_TITLE).classes("text-h3 text-primary")
                ui.markdown("Create audiobooks from text files using local TTS engines.").classes(
                    "q-mb-xl"
                )
                with ui.row().classes("justify-center gap-8"):
                    with ui.card().classes("cursor-pointer col-5") as new_card:
                        ui.label("📖 New Project").classes("text-h5")
                        ui.markdown("Start a fresh audiobook.")
                        ui.tooltip("Begin creating a completely new audiobook")
                        new_card.on("click", lambda: start_new_project())
                    with ui.card().classes("cursor-pointer col-5") as projects_card:
                        ui.label("📚 My Projects").classes("text-h5")
                        ui.markdown("Resume, review, or listen.")
                        ui.tooltip("Manage your existing projects")
                        projects_card.on("click", lambda: show_view("projects"))

        # PIPELINE
        with ui.column().classes("w-full") as pipeline_card:
            pipeline_card.visible = False
            with ui.row().classes("w-full justify-end"):
                ui.button("← Back to Home", on_click=lambda: show_view("home")).props("flat")
            pipeline_step_label = ui.label("").classes("text-subtitle1 q-mb-md")

            # Setup
            with ui.column().classes("w-full") as setup_card:
                ui.label("1. Setup").classes("text-h5 q-mb-md")

                existing_projects = list_projects()
                clone_select = None
                if existing_projects:
                    with ui.row().classes("items-center gap-2 q-mb-md"):
                        ui.label("Clone settings from").classes("text-caption")
                        clone_select = ui.select(
                            options=[""] + existing_projects,
                            value="",
                            on_change=lambda e: clone_settings(e.value),
                        ).classes("w-64")
                        ui.tooltip("Copy configuration from a previous project")

                def clone_settings(project_name: str):
                    if not project_name:
                        return
                    meta_path = OUT_DIR / project_name / "meta.json"
                    if not meta_path.exists():
                        return
                    with meta_path.open("r") as f:
                        meta = json.load(f)
                    source_file = meta.get("source_file", "")
                    book_name = Path(source_file).name if source_file else ""
                    if book_name and (BOOKS_DIR / book_name).exists():
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

                with ui.row().classes("w-full gap-8"):
                    with ui.column().classes("col-12 col-md-6"):
                        ui.label("📖 Source").classes("font-bold")
                        book_select = ui.select(
                            label="Book from books/",
                            options=[""] + list_books(),
                            value="",
                        ).classes("w-full")
                        ui.upload(
                            label="Or upload a .txt file",
                            on_upload=lambda e: on_book_upload(e),
                        ).classes("w-full")
                        output_name = ui.input(
                            label="Output project name", value="my-audiobook"
                        ).classes("w-full")
                    with ui.column().classes("col-12 col-md-6"):
                        ui.label("🎤 Voice").classes("font-bold")
                        backend_radio = ui.radio(
                            ["piper", "xtts"], value="xtts", on_change=lambda: build_voice_widgets()
                        ).props("inline")
                        ui.tooltip(
                            "XTTS offers high‑quality voice cloning; Piper is fast CPU‑based"
                        )
                        voice_container = ui.column().classes("w-full")
                        voice_model_select: Optional[ui.select] = None

                        # Speaker WAV label (shows chosen filename)
                        speaker_label = ui.label("No speaker file selected").classes(
                            "text-caption text-grey"
                        )

                        def build_voice_widgets():
                            nonlocal voice_model_select
                            voice_container.clear()
                            if backend_radio.value == "piper":
                                voice_model_select = ui.select(
                                    label="Piper voice model",
                                    options=[""] + list_voices(),
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
                            options=[
                                "auto",
                                "markdown",
                                "structured",
                                "heuristic",
                                "paragraph",
                                "none",
                            ],
                            value="auto",
                        ).classes("w-full")
                        ui.tooltip("How to split the book into chapters")
                        chapter_confidence = ui.slider(
                            min=0.0, max=1.0, step=0.05, value=0.5
                        ).classes("w-full")
                        ui.label().bind_text_from(
                            chapter_confidence, "value", backward=lambda v: f"Confidence: {v:.2f}"
                        )
                        normalize_check = ui.checkbox("Normalize final book", value=False)
                        target_lufs = ui.number(
                            label="Target LUFS", value=-16.0, step=0.5, format="%.1f"
                        ).bind_visibility_from(normalize_check, "value")

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
                    name = (
                        getattr(e.file, "name", "speaker.wav")
                        if hasattr(e, "file")
                        else "speaker.wav"
                    )
                    speaker_label.set_text(f"✅ {name}")
                    safe_notify(f"Speaker WAV '{name}' uploaded", type="positive")

                # Save button + spinner
                with ui.row().classes("items-center gap-4"):
                    save_btn = ui.button("Save & Continue", on_click=lambda: setup_next()).props(
                        "unelevated color=primary"
                    )
                    setup_spinner = ui.spinner(size="md").props("color=primary")
                    setup_spinner.visible = False

            async def setup_next():
                nonlocal book_event, speaker_event
                # Show spinner, disable button
                setup_spinner.visible = True
                save_btn.disable()
                errors = []
                book_path: Optional[Path] = None
                if book_event is not None:
                    try:
                        book_bytes, book_filename = await extract_upload_bytes(book_event)
                        book_path = TMP_DIR / book_filename
                        book_path.write_bytes(book_bytes)
                    except Exception as e:
                        errors.append(f"Failed to read uploaded book: {e}")
                elif book_select.value:
                    book_path = BOOKS_DIR / book_select.value
                else:
                    errors.append("Please select a book.")
                if not output_name.value.strip():
                    errors.append("Output project name is required.")
                backend = backend_radio.value
                voice_model: Optional[Path] = None
                speaker_wav: Optional[Path] = None
                if backend == "piper":
                    if not voice_model_select or not voice_model_select.value:
                        errors.append("Piper voice model is required.")
                    else:
                        voice_model = VOICES_DIR / voice_model_select.value
                        if not voice_model.exists():
                            errors.append(f"Voice model not found: {voice_model}")
                else:
                    if speaker_event is None:
                        errors.append("XTTS requires a reference speaker WAV upload.")
                    else:
                        try:
                            speaker_bytes, speaker_filename = await extract_upload_bytes(
                                speaker_event
                            )
                            speaker_wav = TMP_DIR / speaker_filename
                            speaker_wav.write_bytes(speaker_bytes)
                        except Exception as e:
                            errors.append(f"Failed to read speaker WAV: {e}")
                if errors:
                    for err in errors:
                        safe_notify(err, type="negative")
                    setup_spinner.visible = False
                    save_btn.enable()
                    return
                try:
                    tts_backend = await run_in_thread(
                        get_backend,
                        backend_type=backend,
                        voice_model=voice_model,
                        speaker_wav=speaker_wav,
                    )
                    proc = IncrementalProcessor(
                        input_file=book_path,
                        output_dir=OUT_DIR / output_name.value.strip(),
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
                    show_pipeline_step("prepare")
                except Exception as e:
                    safe_notify(f"Failed to create processor: {e}", type="negative")
                finally:
                    setup_spinner.visible = False
                    save_btn.enable()

            # Prepare
            with ui.column().classes("w-full") as prepare_card:
                ui.label("2. Prepare Book").classes("text-h5 q-mb-md")
                prepare_status = ui.label("Press the button to analyse the book.")
                with ui.row().classes("items-center gap-4"):
                    prepare_btn = ui.button("Prepare Book", icon="auto_stories")
                    prepare_spinner = ui.spinner(size="md").props("color=primary")
                    prepare_spinner.visible = False

                async def on_prepare():
                    proc = get_processor()
                    if proc is None:
                        safe_notify("No configuration saved.", type="negative")
                        return
                    prepare_btn.disable()
                    prepare_spinner.visible = True
                    try:
                        await run_in_thread(proc.prepare_text)
                        progress = proc.get_progress()
                        prepare_status.set_text(f"✅ {progress.total_chapters} chapters found.")
                        safe_notify("Book prepared!", type="positive")
                        show_pipeline_step("synthesize")
                    except Exception as e:
                        safe_notify(f"Preparation failed: {e}", type="negative")
                    finally:
                        prepare_btn.enable()
                        prepare_spinner.visible = False

                prepare_btn.on_click(lambda: on_prepare())

            # Synthesize (unchanged except minor bindings already present)
            with ui.column().classes("w-full") as synth_card:
                ui.label("3. Synthesize").classes("text-h5 q-mb-md")
                prog = get_progress_dict()
                status_label = ui.label(prog["status_message"])
                overall_progress = ui.linear_progress(value=prog["overall_progress"]).props(
                    "size=20px"
                )
                chapter_progress = ui.linear_progress(value=prog["chapter_progress"]).props(
                    "size=15px color=secondary"
                )
                spinner = ui.spinner(size="lg").props("color=primary")
                spinner.visible = prog.get("active", False)
                chapter_status_html = ui.html(prog["chapter_statuses_html"]).classes("q-mb-md")

                ui.element("div").props("id=processing-indicator").classes("hidden")

                next_btn = ui.button(
                    "Process Next Chapter", icon="skip_next", on_click=lambda: process_one()
                )
                all_btn = ui.button(
                    "Process All Remaining", icon="fast_forward", on_click=lambda: process_all()
                )
                graceful_stop_btn = ui.button(
                    "Stop after current chunk",
                    icon="pause_circle",
                    color="warning",
                    on_click=lambda: graceful_stop(),
                )
                abort_btn = ui.button(
                    "Abort (now)", icon="stop", color="negative", on_click=lambda: abort_now()
                )
                graceful_stop_btn.visible = False
                abort_btn.visible = False

                async def refresh_ui():
                    pd = get_progress_dict()
                    status_label.set_text(pd["status_message"])
                    overall_progress.set_value(pd["overall_progress"])
                    chapter_progress.set_value(pd["chapter_progress"])
                    spinner.visible = pd.get("active", False)
                    chapter_status_html.set_content(pd["chapter_statuses_html"])
                    graceful_stop_btn.visible = pd.get("active", False)
                    abort_btn.visible = pd.get("active", False)
                    next_btn.disable() if pd.get("active") else next_btn.enable()
                    all_btn.disable() if pd.get("active") else all_btn.enable()

                ui.timer(1.0, lambda: refresh_ui())

                async def process_one():
                    await process_chapters(one=True)

                async def process_all():
                    await process_chapters(one=False)

                async def process_chapters(one: bool):
                    proc = get_processor()
                    if proc is None or proc.book_text is None:
                        safe_notify("No prepared book.", type="negative")
                        return
                    set_progress_dict(
                        {
                            "active": True,
                            "overall_progress": 0,
                            "chapter_progress": 0,
                            "status_message": "Starting...",
                            "estimated_time_remaining": "",
                            "chapter_statuses_html": "",
                        }
                    )
                    try:
                        while True:
                            try:
                                await run_in_thread(proc.process_next_chapter)
                            except AbortException:
                                safe_notify("Processing stopped.", type="warning")
                                break
                            update_progress_from_processor(proc)
                            if proc.is_complete():
                                safe_notify("All chapters synthesised!", type="positive")
                                show_pipeline_step("finalize")
                                break
                            if one:
                                break
                            await asyncio.sleep(0.1)
                    except Exception as e:
                        safe_notify(f"Chapter error: {e}", type="negative")
                    finally:
                        set_progress_dict({**get_progress_dict(), "active": False})

                def graceful_stop():
                    proc = get_processor()
                    if proc:
                        proc.request_graceful_stop()

                def abort_now():
                    proc = get_processor()
                    if proc:
                        proc.abort()

            # Finalize
            with ui.column().classes("w-full") as finalize_card:
                ui.label("4. Finalize Book").classes("text-h5 q-mb-md")
                finalize_status = ui.label("Synthesis complete. Click to finalize.")
                finalize_btn = ui.button("Finalize Book", icon="done_all")
                audio_player = ui.audio("").classes("hidden")

                async def on_finalize():
                    proc = get_processor()
                    if proc is None:
                        safe_notify("No active project.", type="negative")
                        return
                    finalize_btn.disable()
                    try:
                        await run_in_thread(proc.finalize_book)
                        book_wav = proc.output_dir / "book.wav"
                        if book_wav.exists():
                            audio_player.set_source(str(book_wav))
                            audio_player.classes(remove="hidden")
                            finalize_status.set_text("✅ Audiobook ready!")
                            safe_notify("Book finalized!", type="positive")
                            show_view("projects")
                    except Exception as e:
                        safe_notify(f"Finalization error: {e}", type="negative")
                    finally:
                        finalize_btn.enable()

                finalize_btn.on_click(lambda: on_finalize())

        # PROJECTS
        with ui.column().classes("w-full") as projects_card:
            projects_card.visible = False
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("📚 My Projects").classes("text-h5")
                ui.button("← Back to Home", on_click=lambda: show_view("home")).props("flat")
            with ui.row().classes("items-center gap-2 q-mb-md"):
                project_select = ui.select(
                    label="Select a project",
                    options=[""] + list_projects(),
                    on_change=lambda e: refresh_review(e.value),
                ).classes("flex-grow")
                ui.button(
                    "Refresh list", icon="refresh", on_click=lambda: refresh_project_list()
                ).props("flat")
            review_area = ui.column()

            def refresh_project_list():
                project_select.options = [""] + list_projects()
                project_select.value = ""
                review_area.clear()

            def refresh_review(project_name: str):
                review_area.clear()
                if not project_name:
                    return
                project_path = OUT_DIR / project_name
                is_incomplete = (project_path / "processing_progress.json").exists() and not (
                    project_path / "meta.json"
                ).exists()
                with review_area:
                    if is_incomplete:
                        ui.label("⚠️ This project is **incomplete**.").classes("text-orange q-mb-sm")
                        ui.button(
                            "Resume Processing", on_click=lambda p=project_name: resume_project(p)
                        ).props("color=orange icon=play_arrow")
                        ui.separator()
                    else:
                        project = BookProject(project_path)
                        meta = project.load_meta()
                        index = project.load_index()
                        ui.label(f"Backend: {meta.get('backend', '?')}  |  Chunks: {len(index)}")
                        book_wav = project_path / "book.wav"
                        if book_wav.exists():
                            ui.audio(str(book_wav)).classes("w-full")
                        chapters = sorted({m["chapter_index"] for m in index})
                        for ch in chapters:
                            ch_wav = project_path / "chapters" / f"chapter_{ch + 1:02d}.wav"
                            with ui.expansion(f"Chapter {ch + 1}", icon="menu_book").classes(
                                "w-full"
                            ):
                                if ch_wav.exists():
                                    ui.audio(str(ch_wav))
                                for m in index:
                                    if m["chapter_index"] == ch:
                                        chunk_wav = project_path / "chunks" / m["file"]
                                        if chunk_wav.exists():
                                            ui.label(f"Chunk {m['id']:05d}").classes("text-caption")
                                            ui.audio(str(chunk_wav))

    # ── View helpers ──
    def show_view(view: str):
        home_card.visible = view == "home"
        projects_card.visible = view == "projects"
        pipeline_card.visible = view == "pipeline"
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
        setup_card.visible = step == "setup"
        prepare_card.visible = step == "prepare"
        synth_card.visible = step == "synthesize"
        finalize_card.visible = step == "finalize"
        pipeline_step_label.set_text(f"Step: {step.title()}")

    # ── Start New Project ──
    def start_new_project():
        set_processor(None)
        book_select.value = ""
        output_name.value = "my-audiobook"
        backend_radio.value = "xtts"  # default to XTTS
        build_voice_widgets()
        preset_select.value = "calm_longform"
        chapter_strategy.value = "auto"
        chapter_confidence.value = 0.5
        normalize_check.value = False
        target_lufs.value = -16.0
        speaker_label.set_text("No speaker file selected")
        show_view("pipeline")
        show_pipeline_step("setup")

    # ── Resume project ──
    async def resume_project(project_name: str):
        progress_file = OUT_DIR / project_name / "processing_progress.json"
        if not progress_file.exists():
            safe_notify("No progress data found.", type="negative")
            return
        try:
            with progress_file.open("r") as f:
                data = json.load(f)
        except Exception as e:
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
            tts_backend = await run_in_thread(
                get_backend,
                backend_type=backend_type,
                voice_model=voice_model,
                speaker_wav=speaker_wav,
            )
        except Exception as e:
            safe_notify(f"Failed to recreate TTS backend: {e}", type="negative")
            return

        try:
            proc = IncrementalProcessor(
                input_file=Path(data["input_file"]),
                output_dir=OUT_DIR / project_name,
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
            await run_in_thread(proc.prepare_text)
            loaded = await run_in_thread(proc.load_progress)
            if not loaded:
                safe_notify("No previous progress could be loaded.", type="warning")
                return
        except Exception as e:
            safe_notify(f"Failed to resume: {e}", type="negative")
            return

        set_processor(proc)
        update_progress_from_processor(proc)
        safe_notify(f"Resumed '{project_name}'", type="positive")
        show_view("pipeline")
        show_pipeline_step("synthesize")

    # ── Initial view ──
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

    # Footer
    ui.markdown("---")
    ui.markdown("Audio‑Files Studio · MIT License · running locally")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=8501,
        title="Audio‑Files Studio",
        favicon="🎙️",
        reload=False,
        show=False,
    )
