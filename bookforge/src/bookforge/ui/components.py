"""
Reusable UI components and shared state helpers.
"""

from __future__ import annotations

import asyncio
from typing import Any

from nicegui import app, ui

# ---------------------------------------------------------------------------
# Notification area
# ---------------------------------------------------------------------------
_notification_container = None

def init_notification_area():
    global _notification_container
    with ui.column().classes("w-full") as _notification_container:
        pass

def safe_notify(msg: str, type: str = "positive"):
    if _notification_container is None:
        ui.notify(msg, type=type, timeout=5)
    else:
        with _notification_container:
            ui.notify(msg, type=type, timeout=5)

# ---------------------------------------------------------------------------
# Processor state (shared across page reloads)
# ---------------------------------------------------------------------------
def get_processor() -> Any | None:
    return app.storage.general.get("processor")

def set_processor(p: Any | None):
    app.storage.general["processor"] = p

# ---------------------------------------------------------------------------
# Progress dictionary helpers
# ---------------------------------------------------------------------------
def get_progress_dict() -> dict:
    return app.storage.general.get("progress", {
        "overall_progress": 0.0,
        "chapter_progress": 0.0,
        "status_message": "Idle",
        "estimated_time_remaining": "",
        "chapter_statuses_html": "",
        "active": False,
    })

def set_progress_dict(d: dict):
    app.storage.general["progress"] = d

def update_progress_from_processor(proc):
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
    html_parts.append('</div>')
    set_progress_dict({
        "overall_progress": progress.overall_progress,
        "chapter_progress": progress.chapter_progress,
        "status_message": f"{progress.status_message} (ETA: {progress.estimated_time_remaining})",
        "estimated_time_remaining": progress.estimated_time_remaining,
        "chapter_statuses_html": ''.join(html_parts),
    })

# ---------------------------------------------------------------------------
# Upload helper
# ---------------------------------------------------------------------------
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