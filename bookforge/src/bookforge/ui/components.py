"""
Reusable UI components and shared state helpers.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
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
# Processor state (persisted as JSON‑safe dict, not the object)
# ---------------------------------------------------------------------------
_processor_cache = None


def get_processor():
    """Return the active processor, reconstructing it from saved state if needed."""
    global _processor_cache
    if _processor_cache is not None:
        return _processor_cache

    state = app.storage.general.get("processor_state")
    if not state:
        return None

    # Reconstruct from persisted state
    from bookforge.incremental_processor import IncrementalProcessor
    from bookforge.tts.factory import get_backend

    backend_type = state.get("backend_type", "piper")
    voice_model = Path(state["voice_model"]) if state.get("voice_model") else None
    speaker_wav = Path(state["speaker_wav"]) if state.get("speaker_wav") else None

    try:
        tts_backend = get_backend(
            backend_type=backend_type,
            voice_model=voice_model,
            speaker_wav=speaker_wav,
        )
    except Exception:
        # Backend may not be available (e.g., missing model) – return None
        return None

    try:
        proc = IncrementalProcessor(
            input_file=Path(state["input_file"]),
            output_dir=Path(state["output_dir"]),
            backend=tts_backend,
            preset=state.get("preset", "calm_longform"),
            chapter_strategy=state.get("chapter_strategy", "auto"),
            chapter_min_confidence=float(state.get("chapter_min_confidence", 0.5)),
            normalize=state.get("normalize", False),
            target_lufs=float(state.get("target_lufs", -16.0)),
            voice_model=voice_model,
            speaker_wav=speaker_wav,
        )
        proc.backend_name = backend_type
        # If there's saved progress, load it
        if (proc.output_dir / "processing_progress.json").exists():
            proc.prepare_text()
            proc.load_progress()
        _processor_cache = proc
        return proc
    except Exception:
        return None


def set_processor(p):
    """Store the processor in cache and persist only serializable state."""
    global _processor_cache
    _processor_cache = p

    if p is None:
        app.storage.general["processor_state"] = None
        return

    app.storage.general["processor_state"] = {
        "input_file": str(p.input_file),
        "output_dir": str(p.output_dir),
        "backend_type": getattr(p, "backend_name", "piper"),
        "voice_model": str(p.voice_model) if p.voice_model else None,
        "speaker_wav": str(p.speaker_wav) if p.speaker_wav else None,
        "preset": p.preset,
        "chapter_strategy": p.chapter_strategy,
        "chapter_min_confidence": p.chapter_min_confidence,
        "normalize": p.normalize,
        "target_lufs": p.target_lufs,
    }


# ---------------------------------------------------------------------------
# Progress dictionary helpers
# ---------------------------------------------------------------------------
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
