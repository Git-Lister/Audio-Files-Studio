"""Audio-Files Studio CLI entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import typer

from .audio.concat import concat_wavs
from .config import PresetConfig
from .ingest.txt_ingest import BookText as TxtBookText
from .ingest.txt_ingest import load_txt
from .process.chunker import Chunk, chunk_chapter
from .process.cleaner import clean_text
from .project import BookProject
from .tts.factory import get_backend

app = typer.Typer(help="Audio-Files Studio: convert texts/epubs into audiobooks using local TTS.")


def _rebuild_audio_from_index(
    project: BookProject,
    index: List[Dict[str, object]],
    skip_first_chunks: int = 0,
) -> None:
    """Rebuild per-chapter WAVs and book.wav from existing chunk WAVs and index."""
    if not index:
        typer.echo("Index is empty; nothing to concatenate.")
        return

    typer.echo("Rebuilding per-chapter WAVs from existing chunks ...")

    sorted_meta = sorted(index, key=lambda m: int(m["id"]))
    if skip_first_chunks > 0:
        typer.echo(f"Skipping first {skip_first_chunks} chunks when concatenating.")
        sorted_meta = sorted_meta[skip_first_chunks:]

    chunks_by_chapter: Dict[int, List[Path]] = {}
    for meta in sorted_meta:
        chapter_idx = int(meta["chapter_index"])
        fname = str(meta["file"])
        wav_path = project.chunks_dir / fname
        if not wav_path.exists():
            continue
        chunks_by_chapter.setdefault(chapter_idx, []).append(wav_path)

    chapter_wavs: List[Path] = []
    for chapter_idx in sorted(chunks_by_chapter.keys()):
        chapter_chunk_files = sorted(chunks_by_chapter[chapter_idx])
        chapter_wav = project.chapters_dir / f"chapter_{chapter_idx + 1:02d}.wav"
        typer.echo(
            f"  Concatenating {len(chapter_chunk_files)} chunks "
            f"for chapter {chapter_idx + 1} → {chapter_wav.name}"
        )
        concat_wavs(chapter_chunk_files, chapter_wav)
        chapter_wavs.append(chapter_wav)

    if chapter_wavs:
        book_wav = project.root / "book.wav"
        typer.echo(f"Concatenating {len(chapter_wavs)} chapter WAVs into {book_wav} ...")
        concat_wavs(chapter_wavs, book_wav)
        typer.echo("Rebuild complete.")
    else:
        typer.echo("No chapter WAVs created during rebuild.")


@app.command()
def process(
    input_file: Path,
    output_dir: Path,
    voice_model: Optional[Path] = typer.Option(
        None,
        "--voice-model",
        "-m",
        help=(
            "Path to Piper ONNX model file "
            "(e.g. en_GB-southern_english_female-medium.onnx). "
            "Required when --backend piper."
        ),
    ),
    backend: str = typer.Option(
        "piper",
        "--backend",
        help="TTS backend to use: 'piper' or 'xtts'",
    ),
    speaker_wav: Optional[Path] = typer.Option(
        None,
        "--speaker-wav",
        help="Optional reference WAV for XTTS voice cloning",
    ),
    preset: str = "calm_longform",
    skip_first_chunks: int = typer.Option(
        0,
        "--skip-first-chunks",
        help="Number of initial chunks to skip when building chapter/book WAVs.",
    ),
    chapter_strategy: str = typer.Option(
        "auto",
        "--chapter-strategy",
        help=(
            "Chapter detection method: "
            "auto (default, tries multiple strategies), "
            "markdown (# headers), "
            "structured (Chapter N, Part I, etc.), "
            "heuristic (contextual scoring), "
            "paragraph (large gaps), "
            "none (single chapter)"
        ),
    ),
    chapter_min_confidence: float = typer.Option(
        0.5,
        "--chapter-min-confidence",
        help="Minimum confidence for chapter detection (0.0-1.0).",
    ),
    normalize: bool = typer.Option(
        False,
        "--normalize",
        help="Apply loudness normalization to final book.wav (EBU R128 standard).",
    ),
    target_lufs: float = typer.Option(
        -16.0,
        "--target-lufs",
        help="Target loudness in LUFS for normalization (default: -16.0 for audiobooks).",
    ),
    incremental: bool = typer.Option(
        False,
        "--incremental",
        help="Use incremental processing (for UI/resumable processing)",
    ),
) -> None:
    """Process INPUT_FILE into an audiobook under OUTPUT_DIR (TXT only for now)."""
    if not input_file.exists():
        raise typer.BadParameter(f"Input file not found: {input_file}")

    output_dir.mkdir(parents=True, exist_ok=True)
    project = BookProject(output_dir)
    config = PresetConfig.load(preset)

    # Shared backend factory
    tts_backend = get_backend(
        backend_type=backend,
        voice_model=voice_model,
        speaker_wav=speaker_wav,
    )

    if incremental:
        from .incremental_processor import IncrementalProcessor

        typer.echo("Using incremental processing mode...")
        processor = IncrementalProcessor(
            input_file=input_file,
            output_dir=output_dir,
            backend=tts_backend,
            preset=preset,
            chapter_strategy=chapter_strategy,
            chapter_min_confidence=chapter_min_confidence,
            normalize=normalize,
            target_lufs=target_lufs,
        )

        typer.echo("📝 Preparing text...")
        processor.prepare_text()
        progress = processor.get_progress()
        typer.echo(f"   Found {progress.total_chapters} chapters")

        typer.echo("🎵 Processing chapters incrementally...")
        while not processor.is_complete():
            processor.process_next_chapter()
            progress = processor.get_progress()
            typer.echo(
                f"   Chapter {progress.current_chapter}/{progress.total_chapters}: "
                f"{progress.status_message}"
            )

        typer.echo("🎉 Finalizing book...")
        processor.finalize_book()
        typer.echo("✅ Incremental processing complete!")

    else:
        typer.echo(f"Loading text from {input_file} ...")

        book: TxtBookText = load_txt(
            input_file,
            chapter_strategy=chapter_strategy,
            min_confidence=chapter_min_confidence,
        )

        typer.echo(f"Title: {book.title}")
        typer.echo(f"Chapters: {len(book.chapters)}")

        if book.chapter_titles:
            typer.echo("\nDetected chapters:")
            for i, title in enumerate(book.chapter_titles[:10]):
                typer.echo(f"  {i + 1}. {title}")
            if len(book.chapter_titles) > 10:
                typer.echo(f"  ... and {len(book.chapter_titles) - 10} more")
            typer.echo("")

        all_chunk_meta: List[Dict[str, object]] = []
        chunk_id = 0

        for chapter_index, chapter_text in enumerate(book.chapters):
            typer.echo(f"Cleaning chapter {chapter_index + 1} ...")
            cleaned = clean_text(chapter_text)

            typer.echo(f"Chunking chapter {chapter_index + 1} ...")
            chunks = chunk_chapter(
                cleaned,
                config,
                chapter_index,
                starting_chunk_id=chunk_id,
            )
            if not chunks:
                continue
            chunk_id = chunks[-1].id + 1

            for chunk in chunks:
                out_wav = project.chunks_dir / f"chunk_{chunk.id:05d}.wav"
                typer.echo(
                    f"  Synthesizing chunk {chunk.id} (chapter {chapter_index + 1}) "
                    f"→ {out_wav.name}"
                )
                tts_backend.synthesize_chunk(chunk, config, out_wav)
                all_chunk_meta.append(chunk.to_dict())

        project.save_index(all_chunk_meta)
        typer.echo(f"Saved project index with {len(all_chunk_meta)} chunks to {project.index_path}")

        project.save_meta(
            {
                "backend": backend,
                "source_file": str(input_file.resolve()),
                "preset": preset,
                "voice_model": str(voice_model) if voice_model else None,
                "speaker_wav": str(speaker_wav) if speaker_wav else None,
                "chapter_strategy": chapter_strategy,
                "chapter_min_confidence": chapter_min_confidence,
                "version": "1.1.0",
            }
        )

        if not all_chunk_meta:
            typer.echo("No chunks generated; nothing to concatenate.")
            return

        _rebuild_audio_from_index(
            project,
            all_chunk_meta,
            skip_first_chunks=skip_first_chunks,
        )
        typer.echo(f"  - {len(all_chunk_meta)} chunk WAVs in {project.chunks_dir}")

        if normalize:
            book_wav = output_dir / "book.wav"
            if book_wav.exists():
                typer.echo(f"\nNormalizing audio to {target_lufs} LUFS ...")
                normalized_wav = output_dir / "book_normalized.wav"

                from .audio.normalise import normalize_audio

                normalize_audio(book_wav, normalized_wav, target_lufs=target_lufs)

                book_wav.unlink()
                normalized_wav.rename(book_wav)
                typer.echo(f"✓ Normalized {book_wav}")
            else:
                typer.echo("Warning: book.wav not found, skipping normalization.")


@app.command()
def review(
    project_dir: Path,
    chunk: int,
    new_text: Optional[str] = typer.Option(
        None,
        "--new-text",
        help="Override text for this chunk; if omitted, reuses current text.",
    ),
    skip_first_chunks: int = typer.Option(
        0,
        "--skip-first-chunks",
        help="Number of initial chunks to skip when rebuilding chapter/book WAVs.",
    ),
) -> None:
    """Review/re-render a specific CHUNK inside an existing project directory."""
    project = BookProject(project_dir)

    index = project.load_index()
    if not index:
        raise typer.BadParameter(f"No project.json found in {project_dir}")

    meta = project.load_meta()
    source_file_str = meta.get("source_file")
    if not source_file_str:
        raise typer.BadParameter(
            f"No source_file recorded in {project.meta_path}; re-run process to create meta.json."
        )

    source_file = Path(source_file_str)
    if not source_file.exists():
        raise typer.BadParameter(f"Source file not found: {source_file}")

    try:
        chunk_meta = next(m for m in index if int(m["id"]) == chunk)
    except StopIteration:
        raise typer.BadParameter(f"Chunk id {chunk} not found in project index.")

    chapter_idx = int(chunk_meta["chapter_index"])

    typer.echo(f"Reloading source text from {source_file} ...")
    chapter_strategy = meta.get("chapter_strategy", "auto")
    min_confidence = float(meta.get("chapter_min_confidence", 0.5))

    book: TxtBookText = load_txt(
        source_file,
        chapter_strategy=chapter_strategy,
        min_confidence=min_confidence,
    )

    if chapter_idx >= len(book.chapters):
        raise typer.BadParameter(f"Chapter index {chapter_idx} out of range for source text.")

    from .process.chunker import chunk_chapter as re_chunk_chapter

    preset_name = str(meta.get("preset", "calm_longform"))
    config = PresetConfig.load(preset_name)

    typer.echo(f"Re-chunking chapter {chapter_idx + 1} to locate chunk {chunk} ...")
    cleaned = clean_text(book.chapters[chapter_idx])
    chapter_chunks: List[Chunk] = re_chunk_chapter(
        cleaned,
        config,
        chapter_idx,
        starting_chunk_id=chunk_meta["id"],
    )

    try:
        original_chunk = next(c for c in chapter_chunks if c.id == chunk)
    except StopIteration:
        raise typer.BadParameter(
            f"Chunk id {chunk} not found when re-chunking chapter {chapter_idx + 1}."
        )

    typer.echo("\nCurrent chunk text (truncated to 400 chars):\n")
    preview = original_chunk.text[:400]
    typer.echo(preview + ("..." if len(original_chunk.text) > 400 else ""))
    typer.echo("")

    updated_text = new_text if new_text is not None else original_chunk.text
    if new_text is not None:
        typer.echo("Using provided --new-text for re-synthesis.")

    updated_chunk = Chunk(
        id=original_chunk.id,
        chapter_index=original_chunk.chapter_index,
        relative_index=original_chunk.relative_index,
        text=updated_text,
        estimated_seconds=original_chunk.estimated_seconds,
    )

    backend_type = str(meta.get("backend", "piper"))
    voice_model = Path(meta["voice_model"]) if meta.get("voice_model") else None
    speaker_wav = Path(meta["speaker_wav"]) if meta.get("speaker_wav") else None

    typer.echo(f"Instantiating {backend_type} backend for re-synthesis...")
    tts_backend = get_backend(
        backend_type=backend_type,
        voice_model=voice_model,
        speaker_wav=speaker_wav,
    )

    out_wav = project.chunks_dir / f"chunk_{updated_chunk.id:05d}.wav"
    typer.echo(f"Re-synthesising chunk {updated_chunk.id} → {out_wav} ...")
    tts_backend.synthesize_chunk(updated_chunk, config, out_wav)

    typer.echo("Rebuilding chapter and book audio after chunk update ...")
    _rebuild_audio_from_index(project, index, skip_first_chunks=skip_first_chunks)


@app.command()
def normalise(
    audio_file: Path,
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: adds '_normalised' suffix to input)",
    ),
    target_lufs: float = typer.Option(
        -16.0,
        "--target-lufs",
        help="Target loudness in LUFS (default: -16.0 for audiobooks).",
    ),
) -> None:
    """Normalise an existing audio file to consistent loudness (EBU R128)."""
    if not audio_file.exists():
        raise typer.BadParameter(f"Audio file not found: {audio_file}")

    if output_file is None:
        output_file = audio_file.parent / f"{audio_file.stem}_normalised{audio_file.suffix}"

    typer.echo(f"Normalising {audio_file} ...")
    typer.echo(f"Target loudness: {target_lufs} LUFS")
    typer.echo("This may take several minutes for large files...")

    from .audio.normalise import normalize_audio

    normalize_audio(audio_file, output_file, target_lufs=target_lufs)

    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    typer.echo("\n✓ Success!")
    typer.echo(f"  Input:  {audio_file}")
    typer.echo(f"  Output: {output_file}")
    typer.echo(f"  Size:   {file_size_mb:.1f} MB")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
