# src/bookforge/ui/voice_library.py
"""Database and file management for the Voice Box (voice library)."""

import json
import sqlite3
import uuid
import shutil
import zipfile
import io
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

DB_PATH = Path("voice_library.db")
USER_VOICES_DIR = Path("user_voices")


def init_db():
    """Create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
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
    ''')
    c.execute('''
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
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_voices_name ON voices(name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_voices_tags ON voices(tags)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)')
    conn.commit()
    conn.close()


def _get_conn():
    return sqlite3.connect(DB_PATH)


def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def add_voice(data: Dict[str, Any]) -> str:
    """Add a new voice to the library. Returns the new UUID."""
    voice_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = _get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO voices (
            id, name, description, reference_wav_path,
            temperature, length_penalty, repetition_penalty,
            top_p, top_k, language, preset_name,
            pitch, rate, normalize, tags, preview_text,
            is_system, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        voice_id,
        data.get('name', 'Unnamed Voice'),
        data.get('description', ''),
        data.get('reference_wav_path'),
        data.get('temperature', 0.667),
        data.get('length_penalty', 1.0),
        data.get('repetition_penalty', 5.0),
        data.get('top_p', 0.8),
        data.get('top_k', 50),
        data.get('language', 'en'),
        data.get('preset_name', 'calm_longform'),
        data.get('pitch', 0.0),
        data.get('rate', 1.0),
        1 if data.get('normalize') else 0,
        data.get('tags', ''),
        data.get('preview_text', 'This is a sample of my voice. It is clear, natural, and ready for narration.'),
        0,  # is_system
        now,
        now
    ))
    conn.commit()
    conn.close()
    return voice_id


def get_voice(voice_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    conn.row_factory = _dict_factory
    c = conn.cursor()
    c.execute('SELECT * FROM voices WHERE id = ?', (voice_id,))
    row = c.fetchone()
    conn.close()
    return row


def list_voices(system: Optional[bool] = None) -> List[Dict[str, Any]]:
    """List all voices; if system is True, only system; if False, only user; if None, all."""
    conn = _get_conn()
    conn.row_factory = _dict_factory
    c = conn.cursor()
    if system is True:
        c.execute('SELECT * FROM voices WHERE is_system = 1 ORDER BY name')
    elif system is False:
        c.execute('SELECT * FROM voices WHERE is_system = 0 ORDER BY name')
    else:
        c.execute('SELECT * FROM voices ORDER BY name')
    rows = c.fetchall()
    conn.close()
    return rows


def update_voice(voice_id: str, data: Dict[str, Any]) -> None:
    now = datetime.now().isoformat()
    conn = _get_conn()
    c = conn.cursor()
    # Build dynamic update query from provided fields
    fields = []
    values = []
    for key in ['name', 'description', 'reference_wav_path', 'temperature', 'length_penalty',
                'repetition_penalty', 'top_p', 'top_k', 'language', 'preset_name',
                'pitch', 'rate', 'normalize', 'tags', 'preview_text']:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return
    values.append(voice_id)
    query = f"UPDATE voices SET {', '.join(fields)}, updated_at = ? WHERE id = ?"
    values.append(now)
    c.execute(query, values)
    conn.commit()
    conn.close()


def delete_voice(voice_id: str) -> bool:
    """Delete a voice from the database and remove its files if user voice."""
    voice = get_voice(voice_id)
    if not voice:
        return False
    if voice['is_system']:
        return False  # cannot delete system voices
    conn = _get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM voices WHERE id = ?', (voice_id,))
    conn.commit()
    conn.close()
    # Remove associated folder
    user_dir = USER_VOICES_DIR / voice_id
    if user_dir.exists():
        shutil.rmtree(user_dir)
    return True


def export_voice(voice_id: str, zip_path: Path) -> None:
    """Export a voice as a .zip file containing voice.json and reference WAV (if any)."""
    voice = get_voice(voice_id)
    if not voice:
        raise ValueError(f"Voice {voice_id} not found")
    # Prepare data (remove internal fields like id, created_at, updated_at, is_system)
    export_data = {k: v for k, v in voice.items()
                   if k not in ['id', 'created_at', 'updated_at', 'is_system']}
    # Create zip in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add voice.json
        zf.writestr('voice.json', json.dumps(export_data, indent=2))
        # Add reference WAV if exists
        ref_path = voice.get('reference_wav_path')
        if ref_path and Path(ref_path).exists():
            zf.write(ref_path, arcname='reference.wav')
    # Write to file
    with open(zip_path, 'wb') as f:
        f.write(zip_buffer.getvalue())


def import_voice(zip_path: Path) -> str:
    """Import a voice from a .zip file (created by export). Returns new UUID."""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Read voice.json
        with zf.open('voice.json') as f:
            data = json.load(f)
        # Extract reference.wav if present
        ref_wav = None
        try:
            with zf.open('reference.wav') as f:
                ref_data = f.read()
                # Save to user_voices/<uuid>/reference.wav
                new_id = str(uuid.uuid4())
                user_dir = USER_VOICES_DIR / new_id
                user_dir.mkdir(parents=True, exist_ok=True)
                ref_wav_path = user_dir / 'reference.wav'
                with open(ref_wav_path, 'wb') as out:
                    out.write(ref_data)
                data['reference_wav_path'] = str(ref_wav_path)
        except KeyError:
            pass  # no reference WAV
        # Add voice to DB
        return add_voice(data)