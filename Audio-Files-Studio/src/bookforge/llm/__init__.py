"""Local LLM engine for optional structured-output inference."""

from __future__ import annotations

from .engine import LLMEngine, get_engine
from .executor import Executor
from .reports import (
    get_run,
    list_runs,
    save_run,
    update_run_decisions,
)
from .schemas import LineDecision, ExecutorResult


def is_available() -> bool:
    """Return True if the LLM stack can be imported and used."""
    try:
        import llama_cpp  # noqa: F401
        return True
    except ImportError:
        return False


__all__ = [
    "LLMEngine",
    "get_engine",
    "Executor",
    "LineDecision",
    "ExecutorResult",
    "is_available",
    "save_run",
    "update_run_decisions",
    "list_runs",
    "get_run",
]