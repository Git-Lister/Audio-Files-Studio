# src/bookforge/ui/state.py
"""Central state management for the UI."""

from __future__ import annotations

from typing import Any

from nicegui import app, ui

from bookforge.incremental_processor import IncrementalProcessor


def _get_storage() -> dict:
    return app.storage.general


def get_state(key: str, default: Any = None) -> Any:
    return _get_storage().get(key, default)


def set_state(key: str, value: Any) -> None:
    _get_storage()[key] = value


# ---- Processor stored in module (NOT in app.storage) ----
_processor: IncrementalProcessor | None = None


def get_processor() -> IncrementalProcessor | None:
    """Get the current processor instance."""
    return _processor


def set_processor(proc: IncrementalProcessor | None) -> None:
    """Set the current processor instance."""
    global _processor
    _processor = proc


# ---- Other state (stored in app.storage) ----
def get_current_view() -> str:
    return get_state("current_view", "home")


def set_current_view(view: str) -> None:
    set_state("current_view", view)


def get_pipeline_step() -> str | None:
    return get_state("pipeline_step", None)


def set_pipeline_step(step: str | None) -> None:
    set_state("pipeline_step", step)


def get_dark_mode() -> bool:
    return get_state("dark_mode", False)


def set_dark_mode(enabled: bool) -> None:
    set_state("dark_mode", enabled)
    ui.dark_mode(enabled)


def get_expert_mode() -> bool:
    return get_state("expert_mode", False)


def set_expert_mode(enabled: bool) -> None:
    set_state("expert_mode", enabled)


# ---- Resume callback (stored in module) ----
_resume_callback = None


def set_resume_callback(callback):
    global _resume_callback
    _resume_callback = callback


def get_resume_callback():
    return _resume_callback
