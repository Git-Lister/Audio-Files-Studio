"""Persistence for LLM runs.

Every Smart Cleanup invocation saves a run: what text was analysed,
what the model proposed, and what the user accepted. Runs are the
raw material for later analysis (Stage 4 Observer, Stage 6 Analyser).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("reports.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the runs table if it doesn't exist."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS llm_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_name TEXT,
            input_hash TEXT NOT NULL,
            input_chars INTEGER NOT NULL,
            model_name TEXT,
            verdicts_json TEXT NOT NULL,
            accepted_json TEXT,
            rejected_json TEXT,
            elapsed_seconds REAL,
            status TEXT DEFAULT 'proposed'
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_runs_created ON llm_runs(created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_runs_hash ON llm_runs(input_hash)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON llm_runs(status)")
    conn.commit()
    conn.close()


init_db()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def save_run(
    input_text: str,
    verdicts: list[dict],
    model_name: str = "",
    source_name: str | None = None,
    elapsed_seconds: float | None = None,
) -> int:
    """Record a new run. Returns the row id."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO llm_runs (
            source_name, input_hash, input_chars, model_name,
            verdicts_json, elapsed_seconds, status
        ) VALUES (?, ?, ?, ?, ?, ?, 'proposed')
        """,
        (
            source_name,
            _hash_text(input_text),
            len(input_text),
            model_name,
            json.dumps(verdicts),
            elapsed_seconds,
        ),
    )
    run_id = c.lastrowid
    conn.commit()
    conn.close()
    return int(run_id)


def update_run_decisions(
    run_id: int,
    accepted: dict[int, str],
    rejected: dict[int, str],
) -> None:
    """Record the user's decisions for a run.

    `accepted` and `rejected` are mappings of line index -> action.
    Status is set to 'decided' if anything was accepted or rejected,
    'discarded' otherwise.
    """
    status = "decided" if (accepted or rejected) else "discarded"
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        """
        UPDATE llm_runs
        SET accepted_json = ?, rejected_json = ?, status = ?
        WHERE id = ?
        """,
        (json.dumps(accepted), json.dumps(rejected), status, run_id),
    )
    conn.commit()
    conn.close()


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent runs, newest first. Used by future UI."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM llm_runs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_run(run_id: int) -> dict[str, Any] | None:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM llm_runs WHERE id = ?", (run_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None