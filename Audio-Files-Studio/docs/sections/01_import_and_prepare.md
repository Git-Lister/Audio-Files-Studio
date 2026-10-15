# Section: Import & Prepare Text

**Status:** Active
**Last updated:** 2026-10-15
**Related commits:** (fill in on first commit)

## Purpose

Turn any document — plain text, PDF, DOCX, EPUB, HTML, Markdown — into
clean, TTS-ready prose. Applies a deterministic phased pipeline of
cleanup rules and optionally a local LLM classification pass. Saves the
result to `books/` for use by the New Project Wizard.

This section exists because synthesis quality depends entirely on
source quality. Garbage in, garbage out. Better to clean once here than
to patch after synthesis.

## User journey

1. Open Import & Prepare from the sidebar.
2. Drag a document onto the upload card, or click to select.
3. The document is extracted (format-specific). Raw text appears in the
   review pane after automatic cleanup runs.
4. Adjust cleanup rules via the Tier 1 / Tier 2 checkboxes if needed.
   Click **Re-Clean** to reapply.
5. Optionally click **Smart Cleanup** — the local LLM proposes line-level
   classifications. Review the modal, accept or reject per item.
6. Edit the review pane manually if needed. Your edits are what gets saved.
7. Click **Save to books/**. The file appears in the wizard's book picker.

## What it reads

- **Source document** — any path the user uploads
- **Rules** — `bookforge.text_extract.cleanup` (`PHASES`, `ALL_RULES`)
- **LLM model** — `/llm-models/Qwen2.5-3B-Instruct-Q4_K_M.gguf` (via `bookforge.llm.engine`)

## What it writes

- **Cleaned text** — `books/<sanitised_name>.txt` (auto-incremented on collision)
- **LLM run record** — `reports.db` (SQLite), one row per Smart Cleanup invocation
- **Temporary** — `temp/import_*.txt` during upload (not cleaned up automatically)

## What it does NOT do

- **Does not synthesise audio.** That is Pipeline.
- **Does not decide voice.** That is Vocalizer and Wizard.
- **Does not edit source files in place.** The original document is never touched.
- **Does not preserve formatting.** Bold, italics, tables, images all discarded.
  Only prose survives.
- **Does not chapter-split.** That happens in Pipeline's chapter detector.
- **Does not automatically fix everything.** Tier 3 (semantic rewrites) is not
  yet implemented. The user is expected to edit if the output isn't sufficient.

## Key interactions

- **Vocalizer** — no direct interaction. Different concern (voice vs text).
- **Wizard** — reads from `books/`. Wizard lists what this section saves.
- **Smart Cleanup** — uses the local LLM engine (`bookforge.llm`), which is
  loaded lazily and shared with future Observer and Analyser tools.
- **Pipeline** — consumes the `.txt` files this section produces.

## Open questions

- Smart Cleanup currently takes a generic prompt. A free-text field for
  user instructions would make it more useful and probably faster
  (fewer tokens if we know what to look for).
- Tier 3 (LLM rewriting) is scheduled but not built.
- Reference-stripping is opt-in. Should it be on by default for academic
  papers? Detection-based defaults would help.

## Changelog

- 2026-10-15 — Initial documentation.