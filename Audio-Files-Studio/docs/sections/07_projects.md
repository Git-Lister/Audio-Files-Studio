# Section: Projects

**Status:** Active — major redesign planned (Batch S)
**Last updated:** 2026-10-15

## Purpose

Browse past and current projects. Resume incomplete ones, play or
re-export completed ones, delete ones that are no longer needed.

Currently under-designed: treats all projects as resumable, which
breaks for completed or empty projects.

## User journey (planned)

1. Open Projects from the sidebar.
2. See a card per project. Each card shows:
   - Project name
   - Book source
   - Voice used
   - Status (In progress / Completed / Failed)
   - Duration, chapters, date for completed projects
3. Actions depend on status:
   - **In progress:** Resume, View Log, Delete
   - **Completed:** Play, View Chapters, Export M4B, Open in Studio, Delete
   - **Failed/Empty:** Delete (or Retry)

## What it reads

- `out/` — list of project directories
- `out/<project>/meta.json` — project metadata
- `out/<project>/book.wav` — completed audio
- `out/<project>/processing_progress.json` — presence indicates an
  incomplete project
- `out/<project>/chapters/` — chapter files

## What it writes

- `app.storage.general["project_active"]` — set when resuming
- `bookforge.ui.state._processor` — set on resume
- Deletes project directories on user confirmation

## What it does NOT do

- **Does not synthesise.** Pipeline does that.
- **Does not edit audio.** Audio Studio does that.
- **Does not manage voice or text files.** Those live in their own
  sections.

## Known issues

- Currently tries to resume every project. Completed projects have no
  `processing_progress.json`, so Resume fails with "No progress data".
  Redesign planned.
- Cannot open a completed project to view or play its output. Redesign
  will fix this.

## Key interactions

- **Pipeline** — Resume navigates to Pipeline with the loaded processor.
- **Audio Studio** — R3 will add "Open output in Studio".
- **Wizard** — creating a new project from Wizard generates an entry
  here once the output directory is created.

## Changelog

- 2026-10-15 — Initial documentation. Redesign planned.