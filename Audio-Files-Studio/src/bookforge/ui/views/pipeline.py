# src/bookforge/ui/views/pipeline.py
"""Unified pipeline view with horizontal stepper: Prepare → Synthesize → Finalize."""

from __future__ import annotations

import asyncio
import json
import subprocess

from nicegui import ui

from bookforge.incremental_processor import AbortException
from bookforge.ui.components import (
    get_processor,
    get_progress_dict,
    safe_notify,
    set_progress_dict,
    update_progress_from_processor,
)
from bookforge.ui.state import get_pipeline_step, set_pipeline_step


class PipelineState:
    def __init__(self, container: ui.column, on_switch_to_projects=None):
        self.container = container
        self.on_switch_to_projects = on_switch_to_projects
        self.step = get_pipeline_step() or "prepare"
        self.stepper: ui.stepper | None = None

        # Content containers
        self.prepare_content: ui.column | None = None
        self.synthesize_content: ui.column | None = None
        self.finalize_content: ui.column | None = None

        # UI elements for dynamic updates
        self.chapter_list: ui.column | None = None
        self.status_label: ui.label | None = None
        self.overall_progress: ui.linear_progress | None = None
        self.chapter_progress: ui.linear_progress | None = None
        self.graceful_stop_btn: ui.button | None = None
        self.abort_btn: ui.button | None = None
        self.next_btn: ui.button | None = None
        self.all_btn: ui.button | None = None

        self.build_ui()

    def build_ui(self):
        self.container.clear()
        with self.container:
            ui.label("📖 Pipeline").classes("text-h5 q-mb-md")

            # Horizontal stepper
            self.stepper = ui.stepper(value=self.step).props("horizontal").classes("w-full")
            with self.stepper:
                # Prepare step
                with ui.step(name="prepare", title="Prepare", icon="library_books"):
                    self.prepare_content = ui.column().classes("w-full")
                    with ui.row().classes("q-mt-md"):
                        ui.button("Next", on_click=lambda: self.go_to_step("synthesize")).props(
                            "color=primary"
                        )

                # Synthesize step
                with ui.step(name="synthesize", title="Synthesize", icon="mic"):
                    self.synthesize_content = ui.column().classes("w-full")
                    with ui.row().classes("q-mt-md"):
                        ui.button("Back", on_click=lambda: self.go_to_step("prepare")).props("flat")
                        ui.button("Next", on_click=lambda: self.go_to_step("finalize")).props(
                            "color=primary"
                        )

                # Finalize step
                with ui.step(name="finalize", title="Finalize", icon="check_circle"):
                    self.finalize_content = ui.column().classes("w-full")
                    with ui.row().classes("q-mt-md"):
                        ui.button("Back", on_click=lambda: self.go_to_step("synthesize")).props(
                            "flat"
                        )
                        ui.button("Projects", on_click=self.go_to_projects).props("color=primary")

            # Render the current step content
            self.render_step(self.step)

    def go_to_step(self, step: str):
        self.step = step
        set_pipeline_step(step)
        if self.stepper:
            self.stepper.value = step
        self.render_step(step)

    def go_to_projects(self):
        if self.on_switch_to_projects:
            self.on_switch_to_projects()
        else:
            if hasattr(self.container, "switch_to_projects") and self.container.switch_to_projects:
                self.container.switch_to_projects()

    def render_step(self, step: str):
        if step == "prepare":
            self.render_prepare()
        elif step == "synthesize":
            self.render_synthesize()
        elif step == "finalize":
            self.render_finalize()

    # ---- Prepare ----
    def render_prepare(self):
        content = self.prepare_content
        if content is None:
            return
        content.clear()
        proc = get_processor()
        with content:
            ui.label("Prepare your book").classes("text-h6")
            if proc is None:
                ui.label("No active project. Start a new one from Home.").classes("text-grey")
                return
            ui.label(f"Book: {proc.input_file.name}").classes("text-caption")
            if proc.book_text is None:
                ui.button("Detect Chapters", on_click=self.detect_chapters).props("color=primary")
                ui.label("Click to detect chapters and prepare text.").classes("text-caption")
            else:
                ui.label(f"Detected {len(proc.book_text.chapters)} chapters.").classes(
                    "text-positive"
                )
                with ui.expansion("View chapters", icon="menu_book").classes("w-full"):
                    for i, ch in enumerate(proc.book_text.chapters):
                        with ui.row().classes("items-center"):
                            ui.label(f"Chapter {i + 1}").classes("text-caption")
                            ui.space()
                            ui.label(f"{len(ch)} characters").classes("text-caption text-grey")

    async def detect_chapters(self):
        proc = get_processor()
        if proc is None:
            return
        await asyncio.to_thread(proc.prepare_text)
        safe_notify("Chapters detected!", type="positive")
        self.render_prepare()

    # ---- Synthesize ----
    def render_synthesize(self):
        content = self.synthesize_content
        if content is None:
            return
        content.clear()
        proc = get_processor()
        with content:
            ui.label("Synthesize your book").classes("text-h6")
            if proc is None:
                ui.label("No active project.").classes("text-grey")
                return
            if proc.book_text is None:
                ui.label("Please prepare the text first (go to Prepare step).").classes(
                    "text-warning"
                )
                return

            pd = get_progress_dict()
            self.overall_progress = ui.linear_progress(value=pd["overall_progress"]).props(
                "size=20px"
            )
            self.status_label = ui.label(pd["status_message"]).classes("text-caption")
            self.chapter_progress = ui.linear_progress(value=pd["chapter_progress"]).props(
                "size=15px color=secondary"
            )

            self.chapter_list = ui.column().classes("w-full q-mt-md")
            self.rebuild_chapter_list()

            with ui.row().classes("items-center gap-2 q-mt-md"):
                self.next_btn = ui.button(
                    "Process Next Chapter", icon="skip_next", on_click=self.process_one
                )
                self.all_btn = ui.button(
                    "Process All", icon="fast_forward", on_click=self.process_all
                )
                ui.button(
                    "Retry Failed", icon="replay", color="warning", on_click=self.retry_failed
                )
                ui.button("View Log", icon="article", on_click=self.show_log)
                self.graceful_stop_btn = ui.button(
                    "Stop after current chunk",
                    icon="pause_circle",
                    color="warning",
                    on_click=self.graceful_stop,
                )
                self.abort_btn = ui.button(
                    "Abort", icon="stop", color="negative", on_click=self.abort_now
                )
                self.graceful_stop_btn.visible = pd.get("active", False)
                self.abort_btn.visible = pd.get("active", False)

            ui.timer(1.0, self.refresh_synthesize_ui)

    def rebuild_chapter_list(self):
        if self.chapter_list is None:
            return
        self.chapter_list.clear()
        proc = get_processor()
        if proc is None:
            return
        statuses = proc.chapter_statuses
        chunks_metadata = proc._chunk_metadata if hasattr(proc, "_chunk_metadata") else []
        with self.chapter_list:
            for status in statuses:
                with ui.card().classes("w-full q-mb-sm"):
                    chapter_idx = status["index"]
                    with ui.row().classes("items-center justify-between"):
                        ui.label(f"Chapter {chapter_idx}").classes("text-h6")
                        if status["error"]:
                            ui.label("❌ Error").classes("text-negative")
                        elif status["processed"]:
                            ui.label("✅ Done").classes("text-positive")
                        else:
                            ui.label("⏳ Pending").classes("text-warning")
                    if status["chunks_total"] > 0:
                        ui.linear_progress(
                            value=status["chunks_done"] / status["chunks_total"]
                        ).props("size=10px color=secondary")
                    if status["error"]:
                        ui.label(status["error"]).classes("text-negative text-caption")
                    chapter_chunks = [
                        c for c in chunks_metadata if c.get("chapter_index") == chapter_idx - 1
                    ]
                    if chapter_chunks:
                        with ui.expansion(f"{len(chapter_chunks)} chunks", icon="list"):
                            for chunk in chapter_chunks:
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(f"Chunk {chunk['id']}").classes("text-caption")
                                    ui.space()
                                    # FIXED: removed size="sm" and used .props('size=sm')
                                    ui.button(
                                        "Re‑synth",
                                        icon="refresh",
                                        on_click=lambda cid=chunk["id"]: self.re_synthesize_chunk(
                                            cid
                                        ),
                                    ).props("flat color=secondary size=sm")

    async def refresh_synthesize_ui(self):
        pd = get_progress_dict()
        if self.status_label is not None:
            self.status_label.set_text(pd["status_message"])
        if self.overall_progress is not None:
            self.overall_progress.set_value(pd["overall_progress"])
        if self.chapter_progress is not None:
            self.chapter_progress.set_value(pd["chapter_progress"])
        if self.graceful_stop_btn is not None:
            self.graceful_stop_btn.visible = pd.get("active", False)
        if self.abort_btn is not None:
            self.abort_btn.visible = pd.get("active", False)
        if self.next_btn is not None:
            self.next_btn.disable() if pd.get("active") else self.next_btn.enable()
        if self.all_btn is not None:
            self.all_btn.disable() if pd.get("active") else self.all_btn.enable()
        self.rebuild_chapter_list()

    async def process_one(self):
        await self.process_chapters(one=True)

    async def process_all(self):
        await self.process_chapters(one=False)

    async def retry_failed(self):
        proc = get_processor()
        if proc is None:
            return
        await asyncio.to_thread(proc.retry_failed_chapters)
        safe_notify("Retrying failed chapters...", type="warning")
        await self.process_all()

    async def process_chapters(self, one: bool):
        proc = get_processor()
        if proc is None or proc.book_text is None:
            safe_notify("No prepared book.", type="negative")
            return
        set_progress_dict({"active": True})
        try:
            while True:
                try:
                    await asyncio.to_thread(proc.process_next_chapter)
                except AbortException:
                    safe_notify("Processing stopped.", type="warning")
                    break
                update_progress_from_processor(proc)
                if proc.is_complete():
                    safe_notify("All chapters synthesised!", type="positive")
                    self.go_to_step("finalize")
                    break
                if one:
                    break
                await asyncio.sleep(0.1)
        except Exception as e:
            safe_notify(f"Error: {e}", type="negative")
        finally:
            set_progress_dict({"active": False})

    def graceful_stop(self):
        proc = get_processor()
        if proc:
            proc.request_graceful_stop()

    def abort_now(self):
        proc = get_processor()
        if proc:
            proc.abort()

    async def show_log(self):
        proc = get_processor()
        if proc is None:
            return
        log_file = proc.output_dir / "processing.log"
        if not log_file.exists():
            safe_notify("No log file.", type="warning")
            return
        try:
            with log_file.open("r") as f:
                lines = f.readlines()[-200:]
            with ui.dialog() as dialog, ui.card().classes("w-3/4 max-w-3xl"):
                ui.label("Processing Log").classes("text-h6")
                with ui.scroll_area().classes("h-96 w-full"):
                    ui.label("".join(lines)).classes("whitespace-pre-line font-mono text-caption")
                ui.button("Close", on_click=dialog.close).props("flat")
            dialog.open()
        except OSError as e:
            safe_notify(f"Failed to read log: {e}", type="negative")

    async def re_synthesize_chunk(self, chunk_id: int):
        proc = get_processor()
        if proc is None:
            return
        try:
            await asyncio.to_thread(proc.re_synthesize_chunk, chunk_id)
            safe_notify(f"Chunk {chunk_id} re‑synthesized.", type="positive")
            update_progress_from_processor(proc)
            self.rebuild_chapter_list()
        except Exception as e:
            safe_notify(f"Re‑synthesis failed: {e}", type="negative")

    # ---- Finalize ----
    def render_finalize(self):
        content = self.finalize_content
        if content is None:
            return
        content.clear()
        proc = get_processor()
        with content:
            ui.label("Finalize your book").classes("text-h6")
            if proc is None:
                ui.label("No active project.").classes("text-grey")
                return
            if not proc.is_complete():
                ui.label("Book not fully synthesised yet. Go back to Synthesize.").classes(
                    "text-warning"
                )
                return

            book_wav = proc.output_dir / "book.wav"
            if book_wav.exists():
                ui.audio(str(book_wav)).classes("w-full")
                ui.button("Export M4B", on_click=self.export_m4b).props("color=secondary")
            else:
                ui.button("Generate book.wav", on_click=self.finalize_book).props("color=primary")

    async def finalize_book(self):
        proc = get_processor()
        if proc is None:
            return
        await asyncio.to_thread(proc.finalize_book)
        safe_notify("book.wav generated!", type="positive")
        self.render_finalize()

    async def export_m4b(self):
        proc = get_processor()
        if proc is None:
            return
        book_wav = proc.output_dir / "book.wav"
        if not book_wav.exists():
            safe_notify("book.wav not found.", type="warning")
            return
        meta_path = proc.output_dir / "meta.json"
        if not meta_path.exists():
            safe_notify("meta.json not found.", type="negative")
            return
        with meta_path.open("r") as f:
            meta = json.load(f)
        chapter_titles = meta.get("chapter_titles", [])
        if not chapter_titles:
            chapter_titles = [f"Chapter {i + 1}" for i in range(len(chapter_titles))]
        chapters_dir = proc.output_dir / "chapters"
        chapter_files = sorted(chapters_dir.glob("chapter_*.wav"))
        if not chapter_files:
            safe_notify("No chapter files found.", type="negative")
            return
        times = [0.0]
        for cf in chapter_files[:-1]:
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        str(cf),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                duration = float(result.stdout.strip())
                times.append(times[-1] + duration)
            except Exception:
                times.append(times[-1] + 60.0)
        chapter_file = proc.output_dir / "chapters.txt"
        with chapter_file.open("w") as f:
            for i, (title, start) in enumerate(zip(chapter_titles, times)):
                f.write(f"CHAPTER{i + 1:02d}={start:.3f}\n")
                f.write(f"CHAPTER{i + 1:02d}NAME={title}\n")
        m4b_path = proc.output_dir / "book.m4b"
        try:
            await asyncio.to_thread(
                subprocess.run,
                [
                    "ffmpeg",
                    "-i",
                    str(book_wav),
                    "-i",
                    str(chapter_file),
                    "-map_metadata",
                    "1",
                    "-map_chapters",
                    "1",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    str(m4b_path),
                    "-y",
                ],
                check=True,
                capture_output=True,
            )
            safe_notify(f"M4B exported: {m4b_path.name}", type="positive")
        except Exception as e:
            safe_notify(f"M4B export failed: {e}", type="negative")


def view(on_switch_to_projects=None):
    container = ui.column().classes("w-full")
    _ = PipelineState(container, on_switch_to_projects=on_switch_to_projects)
    return container
