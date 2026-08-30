# src/bookforge/project.py
"""Project directory management and metadata saving."""

from __future__ import annotations

import json
from pathlib import Path


class BookProject:
    """Manages output directories and saves index/metadata for a book project."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.chunks_dir = output_dir / "chunks"
        self.chapters_dir = output_dir / "chapters"
        # Create directories if they don't exist
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.chapters_dir.mkdir(parents=True, exist_ok=True)

    def save_index(self, chunks: list[dict]) -> None:
        """Save the chunk index (list of dicts) to index.json."""
        index_path = self.output_dir / "index.json"
        with index_path.open("w") as f:
            json.dump(chunks, f, indent=2)

    def save_meta(self, meta: dict) -> None:
        """Save project metadata to meta.json."""
        meta_path = self.output_dir / "meta.json"
        with meta_path.open("w") as f:
            json.dump(meta, f, indent=2)