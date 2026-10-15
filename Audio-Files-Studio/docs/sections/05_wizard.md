# Section: New Project Wizard

**Status:** Active — redesign planned (Batch W)
**Last updated:** 2026-10-15

## Purpose

Set up a new audiobook project: choose a book, choose a voice, name the
project, and hand off to the Pipeline.

Currently a 4-step wizard (Book → Voice → Advanced → Confirm). Planned
redesign: single form.

## User journey (current)

1. Open New Project from the sidebar.
2. **Step 1 — Book:** select from `books/` or upload a `.txt`.
3. **Step 2 — Voice:** pick from Voice Box or upload a reference WAV.
4. **Step 3 — Advanced:** tune temperature, length penalty, repetition
   penalty. *(Redundant — duplicates Vocalizer without preview.)*
5. **Step 4 — Confirm:** name the project, review, click Create.
6. Wizard creates an `IncrementalProcessor` and navigates to Pipeline.

## User journey (planned)

Single form: Book dropdown, Voice dropdown, Preset, Normalize checkbox,
Project name. One click to create. No steps.

## What it reads

- `books/` — book list
- `voice_library.db` — voice list
- `user_voices/<id>/reference.wav` — voice reference WAVs

## What it writes

- `app.storage.general["project_active"] = True`
- `app.storage.general["edit_voice_id"]` — cleared on entry
- Sets the processor via `set_processor()` from `bookforge.ui.components`
- Creates an `IncrementalProcessor` instance (no files yet — output
  directory is created on first synthesis)

## What it does NOT do

- **Does not extract text from documents.** Import & Prepare does that.
- **Does not tune voices.** Vocalizer does that.
- **Does not synthesise.** Pipeline does that.
- **Does not manage projects.** Projects does that.

## Known issues

- Auto-fills `my-audiobook` as the project name. Should require user
  input. Fix planned for Batch S.
- Does not check for existing output directories. Fix planned for Batch S.
- Advanced step duplicates Vocalizer. Planned for removal in Batch W.

## Key interactions

- **Import & Prepare** — produces the `.txt` files the wizard reads.
- **Voice Box** — the wizard's dropdown reads the same DB.
- **Vocalizer** — voices tuned here appear in the wizard.
- **Pipeline** — receives the `IncrementalProcessor` on create.

## Changelog

- 2026-10-15 — Initial documentation. Redesign planned.