"""
Synthesize view – control and monitor chapter synthesis.
"""

from __future__ import annotations

import asyncio

from nicegui import ui

from bookforge.incremental_processor import AbortException
from bookforge.ui.components import (
    get_processor,
    get_progress_dict,
    safe_notify,
    set_progress_dict,
    update_progress_from_processor,
)


def view():
    container = ui.column().classes("w-full")
    with container:
        ui.label("3. Synthesize").classes("text-h5 q-mb-md")
        prog = get_progress_dict()
        status_label = ui.label(prog["status_message"])
        overall_progress = ui.linear_progress(value=prog["overall_progress"]).props("size=20px")
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
        retry_btn = ui.button(
            "Retry Failed Chapters", icon="replay", color="warning", on_click=lambda: retry_failed()
        )
        log_btn = ui.button("View Log", icon="article", on_click=lambda: show_log())
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

        ui.timer(1.0, lambda: refresh_ui())

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

        async def process_one():
            await process_chapters(one=True)

        async def process_all():
            await process_chapters(one=False)

        async def retry_failed():
            proc = get_processor()
            if proc is None:
                safe_notify("No active project.", type="negative")
                return
            await asyncio.to_thread(proc.retry_failed_chapters)
            safe_notify("Failed chapters reset. Starting retry...", type="warning")
            await process_all()

        async def show_log():
            proc = get_processor()
            if proc is None:
                safe_notify("No active project.", type="negative")
                return
            log_file = proc.output_dir / "processing.log"
            if not log_file.exists():
                safe_notify("No log file found.", type="warning")
                return
            try:
                with log_file.open("r") as f:
                    lines = f.readlines()[-200:]
                log_text = "".join(lines)
            except OSError as e:
                safe_notify(f"Failed to read log: {e}", type="negative")
                return

            with ui.dialog() as dialog, ui.card().classes("w-3/4 max-w-3xl"):
                ui.label("Processing Log").classes("text-h6")
                with ui.scroll_area().classes("h-96 w-full"):
                    ui.label(log_text).classes("whitespace-pre-line font-mono text-caption")
                ui.button("Close", on_click=dialog.close).props("flat")
            dialog.open()

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
                        await asyncio.to_thread(proc.process_next_chapter)
                    except AbortException:
                        safe_notify("Processing stopped.", type="warning")
                        break
                    update_progress_from_processor(proc)
                    if proc.is_complete():
                        safe_notify("All chapters synthesised!", type="positive")
                        container.switch_to_finalize()
                        break
                    if one:
                        break
                    await asyncio.sleep(0.1)
            except Exception as e:  # noqa: BLE001
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

    container.switch_to_finalize = None
    return container
