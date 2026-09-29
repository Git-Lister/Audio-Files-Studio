# src/bookforge/ui/voice_library.py
"""Database and file management for the Voice Box (voice library)."""

import io
import json
import shutil
import sqlite3
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("voice_library.db")
USER_VOICES_DIR = Path("user_voices")


def get_voice_dir(voice_id: str) -> Path:
    """Return the canonical directory for a voice's persistent assets."""
    return USER_VOICES_DIR / voice_id


def persist_reference(voice_id: str, source_path: Path) -> Path:
    """Copy a reference WAV into the voice's persistent directory.

    Returns the destination path. Creates the directory if needed.
    """
    dest_dir = get_voice_dir(voice_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "reference.wav"
    shutil.copy(source_path, dest)
    return dest


def get_preview_path(voice_id: str) -> Path:
    """Return the canonical preview WAV path for a voice (may not exist)."""
    return get_voice_dir(voice_id) / "preview.wav"


def init_db():
    """Create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS voices (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            reference_wav_path TEXT,
            temperature REAL DEFAULT 0.667,
            length_penalty REAL DEFAULT 1.0,
            repetition_penalty REAL DEFAULT 5.0,
            top_p REAL DEFAULT 0.8,
            top_k INTEGER DEFAULT 50,
            language TEXT DEFAULT 'en',
            preset_name TEXT DEFAULT 'calm_longform',
            pitch REAL DEFAULT 0.0,
            rate REAL DEFAULT 1.0,
            normalize INTEGER DEFAULT 0,
            tags TEXT,
            preview_text TEXT DEFAULT 'This is a sample of my voice. It is clear, natural, and ready for narration.',
            is_system INTEGER DEFAULT 0,
            created_at DATETIME,
            updated_at DATETIME
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            output_dir TEXT NOT NULL,
            voice_id TEXT,
            status TEXT,
            total_duration REAL,
            chapter_count INTEGER,
            created_at DATETIME,
            updated_at DATETIME
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_voices_name ON voices(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_voices_tags ON voices(tags)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)")
    conn.commit()
    conn.close()


# ---- Ensure tables exist when this module is loaded ----
init_db()


def _get_conn():
    return sqlite3.connect(DB_PATH)


def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def add_voice(data: Dict[str, Any]) -> str:
    voice_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO voices (
            id, name, description, reference_wav_path,
            temperature, length_penalty, repetition_penalty,
            top_p, top_k, language, preset_name,
            pitch, rate, normalize, tags, preview_text,
            is_system, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            voice_id,
            data.get("name", "Unnamed Voice"),
            data.get("description", ""),
            data.get("reference_wav_path"),
            data.get("temperature", 0.667),
            data.get("length_penalty", 1.0),
            data.get("repetition_penalty", 5.0),
            data.get("top_p", 0.8),
            data.get("top_k", 50),
            data.get("language", "en"),
            data.get("preset_name", "calm_longform"),
            data.get("pitch", 0.0),
            data.get("rate", 1.0),
            1 if data.get("normalize") else 0,
            data.get("tags", ""),
            data.get(
                "preview_text",
                "This is a sample of my voice. It is clear, natural, and ready for narration.",
            ),
            0,  # is_system
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return voice_id


def get_voice(voice_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    conn.row_factory = _dict_factory
    c = conn.cursor()
    c.execute("SELECT * FROM voices WHERE id = ?", (voice_id,))
    row = c.fetchone()
    conn.close()
    return row


def list_voices(system: Optional[bool] = None) -> List[Dict[str, Any]]:
    conn = _get_conn()
    conn.row_factory = _dict_factory
    c = conn.cursor()
    if system is True:
        c.execute("SELECT * FROM voices WHERE is_system = 1 ORDER BY name")
    elif system is False:
        c.execute("SELECT * FROM voices WHERE is_system = 0 ORDER BY name")
    else:
        c.execute("SELECT * FROM voices ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return rows


def update_voice(voice_id: str, data: Dict[str, Any]) -> None:
    now = datetime.now().isoformat()
    conn = _get_conn()
    c = conn.cursor()
    fields = []
    values = []
    for key in [
        "name",
        "description",
        "reference_wav_path",
        "temperature",
        "length_penalty",
        "repetition_penalty",
        "top_p",
        "top_k",
        "language",
        "preset_name",
        "pitch",
        "rate",
        "normalize",
        "tags",
        "preview_text",
    ]:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return
    values.append(now)
    query = f"UPDATE voices SET {', '.join(fields)}, updated_at = ? WHERE id = ?"
    values.append(voice_id)
    c.execute(query, values)
    conn.commit()
    conn.close()


def delete_voice(voice_id: str) -> bool:
    voice = get_voice(voice_id)
    if not voice:
        return False
    if voice["is_system"]:
        return False
    conn = _get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM voices WHERE id = ?", (voice_id,))
    conn.commit()
    conn.close()
    user_dir = USER_VOICES_DIR / voice_id
    if user_dir.exists():
        shutil.rmtree(user_dir)
    return True


def export_voice(voice_id: str, zip_path: Path) -> None:
    voice = get_voice(voice_id)
    if not voice:
        raise ValueError(f"Voice {voice_id} not found")
    export_data = {
        k: v for k, v in voice.items() if k not in ["id", "created_at", "updated_at", "is_system"]
    }
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("voice.json", json.dumps(export_data, indent=2))
        ref_path = voice.get("reference_wav_path")
        if ref_path and Path(ref_path).exists():
            zf.write(ref_path, arcname="reference.wav")
        preview_path = get_preview_path(voice_id)
        if preview_path.exists():
            zf.write(preview_path, arcname="preview.wav")
    with open(zip_path, "wb") as f:
        f.write(zip_buffer.getvalue())


def import_voice(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("voice.json") as f:
            data = json.load(f)
        new_id = str(uuid.uuid4())
        user_dir = USER_VOICES_DIR / new_id
        user_dir.mkdir(parents=True, exist_ok=True)

        # Extract reference.wav if present
        try:
            with zf.open("reference.wav") as f:
                ref_data = f.read()
                ref_wav_path = user_dir / "reference.wav"
                with open(ref_wav_path, "wb") as out:
                    out.write(ref_data)
                data["reference_wav_path"] = str(ref_wav_path)
        except KeyError:
            pass

        # Extract preview.wav if present
        try:
            with zf.open("preview.wav") as f:
                preview_data = f.read()
                preview_path = get_preview_path(new_id)
                preview_path.parent.mkdir(parents=True, exist_ok=True)
                with open(preview_path, "wb") as out:
                    out.write(preview_data)
        except KeyError:
            pass

        return add_voice(data)
