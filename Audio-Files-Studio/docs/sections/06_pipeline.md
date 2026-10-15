# Section: Pipeline

**Status:** Active
**Last updated:** 2026-10-15

## Purpose

The synthesis engine. Takes the project set up by the Wizard and turns
it into audio: chapter detection, chunk splitting, synthesis per chunk,
concatenation into chapters, concatenation into `book.wav`, optional
loudness normalization, and M4B export.

## User journey

1. Arrive from Wizard (or from Projects via Resume).
2. **Prepare:** click Detect Chapters. Text is split.
3. **Synthesize:** Process Next Chapter, Process All, or per-chapter.
   Progress bars and status messages update live.
4. **Finalize:** Generate book.wav, then Export M4B.
5. Save: output is under `out/<project>/`.

## What it reads

- `IncrementalProcessor` — from `bookforge.ui.state`
- `out/<project>/processing_progress.json` — on resume
- `out/<project>/chunks_index.json` — chunk metadata on resume
- Preset config via `bookforge.config.PresetConfig`

## What it writes

- `out/<project>/chapters/chapter_NN.wav` — one per chapter
- `out/<project>/chunks/chunk_NNNNN.wav` — one per chunk
- `out/<project>/book.wav` — final concatenation
- `out/<project>/book.m4b` — on M4B export
- `out/<project>/meta.json` — project metadata
- `out/<project>/chunks_index.json` — chunk history
- `out/<project>/processing_progress.json` — resumable state (deleted
  on successful finalize)
- `out/<project>/processing.log` — debug log

## What it does NOT do

- **Does not pick a voice.** Wizard does that.
- **Does not tune parameters.** Vocalizer does that.
- **Does not edit output.** Audio Studio does that (R3 integration).
- **Does not decide text cleanup.** Import & Prepare does that.

## Known issues

- `chunks_index.json` is not reset when a new run begins in an existing
  output directory. Causes stale counts and inconsistent state. Fix
  planned for Batch S.
- The voice parameter sliders in the Synthesize step duplicate
  Vocalizer without preview. Planned for removal in Batch V.
- Chapter cards cannot be expanded during processing to inspect chunk
  status. Fix pending.

## Key interactions

- **Wizard** — receives the processor on create.
- **Projects** — writes the output directory and metadata that Projects
  reads for its cards.
- **Audio Studio** — R3 will let users open chapter WAVs for editing.

## Changelog

- 2026-10-15 — Initial documentation.