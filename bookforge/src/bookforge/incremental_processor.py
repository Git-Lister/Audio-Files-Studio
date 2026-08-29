# Incremental Book Processing for UI

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .audio.concat import concat_wavs
from .config import PresetConfig
from .ingest.txt_ingest import BookText, load_txt
from .process.chunker import Chunk, chunk_chapter
from .process.cleaner import clean_text
from .project import BookProject
from .tts.backend import TTSBackend


class AbortException(Exception):
    """Raised when processing is aborted by the user."""

    pass


@dataclass
class ProcessingProgress:
    stage: str
    current_chapter: int
    total_chapters: int
    current_chunk: int
    total_chunks: int
    chapter_progress: float
    overall_progress: float
    estimated_time_remaining: str
    status_message: str
    start_time: datetime
    elapsed_time: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "current_chapter": self.current_chapter,
            "total_chapters": self.total_chapters,
            "current_chunk": self.current_chunk,
            "total_chunks": self.total_chunks,
            "chapter_progress": self.chapter_progress,
            "overall_progress": self.overall_progress,
            "estimated_time_remaining": self.estimated_time_remaining,
            "status_message": self.status_message,
            "start_time": self.start_time.isoformat(),
            "elapsed_time": self.elapsed_time,
        }


@dataclass
class ChapterProgress:
    chapter_index: int
    cleaned_text: str
    chunks: List[Chunk] = field(default_factory=list)
    processed_chunks: int = 0
    chapter_audio_created: bool = False
    error_message: Optional[str] = None


class IncrementalProcessor:
    def __init__(
        self,
        input_file: Path,
        output_dir: Path,
        backend: TTSBackend,
        preset: str = "calm_longform",
        chapter_strategy: str = "auto",
        chapter_min_confidence: float = 0.5,
        normalize: bool = False,
        target_lufs: float = -16.0,
        voice_model: Optional[Path] = None,
        speaker_wav: Optional[Path] = None,
    ):
        self.input_file = input_file
        self.output_dir = output_dir
        self.backend = backend
        self.backend_name = "unknown"
        self.preset = preset
        self.chapter_strategy = chapter_strategy
        self.chapter_min_confidence = chapter_min_confidence
        self.normalize = normalize
        self.target_lufs = target_lufs

        # Store voice info for resumption
        self.voice_model = voice_model
        self.speaker_wav = speaker_wav

        self.project = BookProject(output_dir)
        self.config = PresetConfig.load(preset)

        self.book_text: Optional[BookText] = None
        self.chapter_progress: List[ChapterProgress] = []
        self.all_chunks: List[Chunk] = []
        self.start_time = datetime.now()
        self.stop_requested = False
        self.graceful_stop_requested = False  # <-- add this line

        # Logging
        self.logger = logging.getLogger("bookforge.processor")
        self.logger.setLevel(logging.DEBUG)
        log_file = output_dir / "processing.log"
        log_file.unlink(missing_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logger.info(f"Processor initialised for {input_file}")

        self.progress_file = output_dir / "processing_progress.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def abort(self):
        self.stop_requested = True
        self.logger.warning("Abort requested by user")

    def request_graceful_stop(self):
        """Request processing to stop after the current chunk finishes."""
        self.graceful_stop_requested = True
        self.logger.info("Graceful stop requested")

    def prepare_text(self) -> None:
        if self.book_text is not None:
            return
        self.logger.info("Preparing text...")
        self.book_text = load_txt(
            self.input_file,
            chapter_strategy=self.chapter_strategy,
            min_confidence=self.chapter_min_confidence,
        )
        self.chapter_progress = [
            ChapterProgress(chapter_index=i, cleaned_text=clean_text(ch))
            for i, ch in enumerate(self.book_text.chapters)
        ]
        self.logger.info(f"Found {len(self.chapter_progress)} chapters")
        self._save_progress()

    def process_next_chapter(self) -> bool:
        if self.stop_requested:
            self.logger.info("Stop requested, skipping")
            raise AbortException("Processing aborted")
        if self.book_text is None:
            raise ValueError("Must call prepare_text() first")

        for cp in self.chapter_progress:
            if not cp.chapter_audio_created and cp.error_message is None:
                self._process_chapter(cp)
                self._save_progress()
                return True
        return False

    def retry_failed_chapters(self) -> None:
        """Reset all chapters with errors so they can be processed again."""
        self.logger.info("Retrying failed chapters...")
        for cp in self.chapter_progress:
            if cp.error_message:
                cp.error_message = None
                cp.processed_chunks = 0
                cp.chapter_audio_created = False
                cp.chunks = []  # force re-chunking
        self._save_progress()
        self.logger.info("Failed chapters reset for retry.")

    def finalize_book(self) -> None:
        if not self.is_complete():
            raise ValueError("Cannot finalize: processing not complete")
        self.logger.info("Finalizing book...")
        chapter_wavs = [
            self.project.chapters_dir / f"chapter_{i + 1:02d}.wav"
            for i in range(len(self.chapter_progress))
        ]
        if chapter_wavs:
            book_wav = self.output_dir / "book.wav"
            concat_wavs(chapter_wavs, book_wav)
            if self.normalize:
                from .audio.normalise import normalize_audio

                normalized_wav = self.output_dir / "book_normalized.wav"
                normalize_audio(book_wav, normalized_wav, target_lufs=self.target_lufs)
                book_wav.unlink()
                normalized_wav.rename(book_wav)

        chunk_dicts = [chunk.to_dict() for chunk in self.all_chunks]
        self.project.save_index(chunk_dicts)
        self.project.save_meta(
            {
                "backend": self.backend_name,
                "source_file": str(self.input_file.resolve()),
                "preset": self.preset,
                "chapter_strategy": self.chapter_strategy,
                "chapter_min_confidence": self.chapter_min_confidence,
                "normalize": self.normalize,
                "target_lufs": self.target_lufs,
                "chapter_titles": self.book_text.chapter_titles if self.book_text else [],
                "version": "1.2.0",
                "processing_completed": datetime.now().isoformat(),
            }
        )
        if self.progress_file.exists():
            self.progress_file.unlink()
        self.logger.info("Finalization complete")

    def is_complete(self) -> bool:
        return self.book_text is not None and all(
            cp.chapter_audio_created for cp in self.chapter_progress
        )

    # ------------------------------------------------------------------
    # Progress helpers
    # ------------------------------------------------------------------
    def get_progress(self) -> ProcessingProgress:
        if not self.book_text or not self.chapter_progress:
            return ProcessingProgress(
                stage="preparing_text",
                current_chapter=0,
                total_chapters=0,
                current_chunk=0,
                total_chunks=0,
                chapter_progress=0.0,
                overall_progress=0.0,
                estimated_time_remaining="Unknown",
                status_message="Preparing text...",
                start_time=self.start_time,
                elapsed_time=self._format_elapsed_time(),
            )

        total_chapters = len(self.chapter_progress)
        completed_chapters = sum(1 for cp in self.chapter_progress if cp.chapter_audio_created)
        current_chapter_idx = 0
        current_chunk_total = 0
        current_chunk_done = 0
        for i, cp in enumerate(self.chapter_progress):
            if not cp.chapter_audio_created and cp.error_message is None:
                current_chapter_idx = i
                current_chunk_total = len(cp.chunks)
                current_chunk_done = cp.processed_chunks
                break
        else:
            current_chapter_idx = total_chapters

        chapter_progress = (
            current_chunk_done / max(current_chunk_total, 1) if current_chunk_total else 1.0
        )
        overall_progress = (completed_chapters + chapter_progress) / max(total_chapters, 1)

        elapsed = (datetime.now() - self.start_time).total_seconds()
        if overall_progress > 0:
            total_est = elapsed / overall_progress
            remaining = total_est - elapsed
            eta = self._format_time_remaining(remaining)
        else:
            eta = "Calculating..."

        if current_chapter_idx >= total_chapters:
            status = "All chapters processed"
        elif current_chunk_total == 0:
            status = f"Preparing chapter {current_chapter_idx + 1}/{total_chapters}"
        else:
            status = f"Synthesizing chunk {current_chunk_done + 1}/{current_chunk_total} in Chapter {current_chapter_idx + 1}"

        return ProcessingProgress(
            stage="processing_chapters",
            current_chapter=current_chapter_idx + 1,
            total_chapters=total_chapters,
            current_chunk=current_chunk_done + 1,
            total_chunks=current_chunk_total,
            chapter_progress=chapter_progress,
            overall_progress=overall_progress,
            estimated_time_remaining=eta,
            status_message=status,
            start_time=self.start_time,
            elapsed_time=self._format_elapsed_time(),
        )

    @property
    def chapter_statuses(self) -> List[Dict[str, Any]]:
        if not self.chapter_progress:
            return []
        return [
            {
                "index": cp.chapter_index + 1,
                "processed": cp.chapter_audio_created,
                "error": cp.error_message or "",
                "chunks_done": cp.processed_chunks,
                "chunks_total": len(cp.chunks),
            }
            for cp in self.chapter_progress
        ]

    # ------------------------------------------------------------------
    # Resume support
    # ------------------------------------------------------------------
    def load_progress(self) -> bool:
        """Load saved progress from processing_progress.json. Returns True if loaded."""
        if not self.progress_file.exists():
            return False
        with self.progress_file.open("r") as f:
            data = json.load(f)

        # Restore voice info (if present)
        self.backend_name = data.get("backend_name", self.backend_name)
        if data.get("voice_model"):
            self.voice_model = Path(data["voice_model"])
        if data.get("speaker_wav"):
            self.speaker_wav = Path(data["speaker_wav"])

        # Ensure text is prepared
        if self.book_text is None:
            self.prepare_text()

        # Restore chapter progress
        saved_cp = data.get("chapter_progress", [])
        for i, cp in enumerate(self.chapter_progress):
            if i < len(saved_cp):
                cp.processed_chunks = saved_cp[i].get("processed_chunks", 0)
                cp.chapter_audio_created = saved_cp[i].get("chapter_audio_created", False)
                cp.error_message = saved_cp[i].get("error_message", None)
                # Rebuild chunk list if missing
                if not cp.chunks and cp.cleaned_text:
                    starting_id = (
                        len(self.all_chunks)
                        if self.all_chunks
                        else saved_cp[i].get("chunks_count", 0)
                    )
                    cp.chunks = chunk_chapter(
                        cp.cleaned_text,
                        self.config,
                        cp.chapter_index,
                        starting_chunk_id=starting_id,
                    )
        self.logger.info("Resumed progress from previous session")
        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _process_chapter(self, cp: ChapterProgress) -> None:
        chapter_idx = cp.chapter_index
        self.logger.info(f"Starting chapter {chapter_idx + 1}/{len(self.chapter_progress)}")

        if not cp.chunks:
            starting_chunk_id = len(self.all_chunks)
            cp.chunks = chunk_chapter(
                cp.cleaned_text,
                self.config,
                chapter_idx,
                starting_chunk_id=starting_chunk_id,
            )

        chunk_wav_files = []
        for chunk in cp.chunks:
            if cp.processed_chunks >= len(cp.chunks):
                continue
            if self.stop_requested:
                self.logger.warning(f"Aborting during chapter {chapter_idx + 1} chunk {chunk.id}")
                raise AbortException("Processing aborted")

            out_wav = self.project.chunks_dir / f"chunk_{chunk.id:05d}.wav"
            try:
                self.backend.synthesize_chunk(chunk, self.config, out_wav)
                chunk_wav_files.append(out_wav)
                cp.processed_chunks += 1
                self.all_chunks.append(chunk)
                # Check for graceful stop after completing the current chunk
                if self.graceful_stop_requested:
                    self._save_progress()
                    self.stop_requested = True
                    raise AbortException("Processing stopped after current chunk")

                self.logger.debug(f"Chunk {chunk.id} done")
            except Exception as e:
                cp.error_message = f"Chunk {chunk.id}: {e}"
                self.logger.error(f"Error in chapter {chapter_idx + 1} chunk {chunk.id}: {e}")
                raise

        if chunk_wav_files and not cp.chapter_audio_created:
            chapter_wav = self.project.chapters_dir / f"chapter_{chapter_idx + 1:02d}.wav"
            concat_wavs(chunk_wav_files, chapter_wav)
            cp.chapter_audio_created = True
            self.logger.info(f"Chapter {chapter_idx + 1} complete")

    def _save_progress(self) -> None:
        progress_data = {
            "input_file": str(self.input_file),
            "output_dir": str(self.output_dir),
            "backend_name": self.backend_name,
            "voice_model": str(self.voice_model) if self.voice_model else None,
            "speaker_wav": str(self.speaker_wav) if self.speaker_wav else None,
            "preset": self.preset,
            "chapter_strategy": self.chapter_strategy,
            "chapter_min_confidence": self.chapter_min_confidence,
            "normalize": self.normalize,
            "target_lufs": self.target_lufs,
            "chapter_progress": [
                {
                    "chapter_index": cp.chapter_index,
                    "processed_chunks": cp.processed_chunks,
                    "chapter_audio_created": cp.chapter_audio_created,
                    "error_message": cp.error_message,
                    "chunks_count": len(cp.chunks),
                }
                for cp in self.chapter_progress
            ],
            "all_chunks_count": len(self.all_chunks),
            "start_time": self.start_time.isoformat(),
        }
        with self.progress_file.open("w") as f:
            json.dump(progress_data, f, indent=2)

    def _format_time_remaining(self, seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}h {mins}m"

    def _format_elapsed_time(self) -> str:
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return self._format_time_remaining(elapsed)
