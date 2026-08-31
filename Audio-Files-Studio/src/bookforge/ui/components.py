# src/bookforge/ui/components.py
"""Shared UI components and helpers."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from nicegui import ui

from bookforge.incremental_processor import IncrementalProcessor
from bookforge.ui import state

# ---- Notification storage ----
_notifications: list[dict] = []  # each dict: {"message": str, "type": str, "timestamp": float}
_notification_panel: ui.column | None = None


def add_notification(message: str, type: str = "info") -> None:
    """Add a notification to the persistent list and update the panel."""
    _notifications.append({"message": message, "type": type, "timestamp": time.time()})
    if len(_notifications) > 20:
        _notifications.pop(0)
    update_notification_panel()


def update_notification_panel() -> None:
    """Refresh the persistent notification panel."""
    if _notification_panel is None:
        return
    _notification_panel.clear()
    with _notification_panel:
        ui.label("📢 Notifications").classes("text-subtitle1")
        for notif in _notifications[-5:]:  # Show last 5
            color = {
                "positive": "text-positive",
                "negative": "text-negative",
                "warning": "text-warning",
                "info": "text-primary",
            }.get(notif["type"], "text-grey")
            ui.label(f"[{notif['type'].upper()}] {notif['message']}").classes(
                f"text-caption {color}"
            )


def safe_notify(message: str, type: str = "info") -> None:
    """Show a toast and add to persistent panel."""
    add_notification(message, type)
    if type == "positive":
        ui.notify(message, type="positive", position="top-right")
    elif type == "negative":
        ui.notify(message, type="negative", position="top-right")
    elif type == "warning":
        ui.notify(message, type="warning", position="top-right")
    else:
        ui.notify(message, type="info", position="top-right")


def init_notification_area() -> None:
    """Initialize the notification area – called once at startup."""
    # The panel is created in main.py; we just need to ensure the reference is set.
    pass


# ---- Processor helpers ----
def get_processor() -> IncrementalProcessor | None:
    return state.get_processor()


def set_processor(proc: IncrementalProcessor | None) -> None:
    state.set_processor(proc)


# ---- Progress helpers ----
def get_progress_dict() -> dict[str, Any]:
    proc = get_processor()
    if proc is None:
        return {
            "active": False,
            "overall_progress": 0.0,
            "chapter_progress": 0.0,
            "status_message": "No active project.",
            "chapter_statuses_html": "",
        }
    progress = proc.get_progress()
    # Build HTML for chapter statuses
    statuses = proc.chapter_statuses
    html = "<ul>"
    for s in statuses:
        icon = "✅" if s["processed"] else "⏳" if s["error"] else "⬜"
        html += f"<li>Chapter {s['index']}: {icon} {s['chunks_done']}/{s['chunks_total']}</li>"
    html += "</ul>"
    return {
        "active": False,  # will be set by the processing loop
        "overall_progress": progress.overall_progress,
        "chapter_progress": progress.chapter_progress,
        "status_message": progress.status_message,
        "chapter_statuses_html": html,
    }


def set_progress_dict(data: dict[str, Any]) -> None:
    # This is used to store processing state; we'll use a global variable.
    # For simplicity, we'll store in app.storage.
    state.set_state("progress", data)


def update_progress_from_processor(proc: IncrementalProcessor) -> None:
    progress = proc.get_progress()
    set_progress_dict(
        {
            "overall_progress": progress.overall_progress,
            "chapter_progress": progress.chapter_progress,
            "status_message": progress.status_message,
            "active": True,
            "chapter_statuses_html": "",
        }
    )
    # Also update the notification panel with status if needed
    safe_notify(progress.status_message, type="info")


# ---- File upload helpers ----
async def extract_upload_bytes(upload_event) -> tuple[bytes, str]:
    """Extract bytes and filename from a NiceGUI upload event."""
    if hasattr(upload_event, "file"):
        # For files uploaded via ui.upload
        content = await upload_event.file.read()
        name = getattr(upload_event.file, "name", "uploaded_file")
        return content, name
    else:
        # Fallback
        return b"", "unknown"
