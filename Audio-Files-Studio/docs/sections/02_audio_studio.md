# Section: Audio Studio

**Status:** Active (R1 — core editing shipped; R2/R3 pending)
**Last updated:** 2026-10-15

## Purpose

A single workspace for audio editing. Four jobs share this view:

1. Clean up reference recordings before voice cloning
2. Polish generated output (fix artifacts, splice takes)
3. Combine multiple clips into one
4. Convert formats

Currently implemented: single-file load, waveform, playhead, selection,
trim, delete, undo, export as WAV.

## User journey

1. Open Audio Studio from the sidebar.
2. Upload an audio file (any format ffmpeg reads).
3. Waveform renders. Metadata line shows duration, sample rate, channels.
4. Play, pause, or click on the waveform to seek.
5. Drag to select a region. Selection highlight appears.
6. Apply an operation (currently: Trim to selection, Delete selection).
7. Undo/redo as needed.
8. Export to `audio_edits/<name>.wav`.

## What it reads

- Any audio file the user uploads, via a temp working copy
- `ffprobe` for metadata
- `ffmpeg` for peak extraction and edit operations

## What it writes

- `temp/studio/working_<uuid>.wav` — the current working file
- `temp/studio/sessions/<uuid>/snap_NNNN.wav` — undo snapshots
- `audio_edits/<name>.wav` — user exports

## What it does NOT do

- **Does not synthesise.** It edits existing audio.
- **Does not touch files in place.** The source file is never modified.
- **Does not multi-track.** Single file at a time, v1.
- **Does not do spectral editing.** Waveform view only.
- **Does not process video.**
- **Does not persist state.** Sessions are ephemeral.

## Key interactions

- **Voice Box** — R3 will add "Edit reference" that opens Studio with
  a voice's `reference.wav` loaded.
- **Vocalizer** — R3 will add "Edit in Studio" link from the reference
  status label.
- **Pipeline** — R3 will add "Open chapter in Studio" from Finalize.
- **Projects** — R3 will add "Open output in Studio".

## Open questions

- Multi-clip list model for combining takes (R3).
- Fades, normalize, silence trim, format conversion (R2).
- Whether Media Lab (format conversion utility) folds into Studio or
  stays separate. Leaning toward fold-in.

## Changelog

- 2026-10-15 — R1 shipped: single-file editing.