# Section: Settings

**Status:** Active
**Last updated:** 2026-10-15

## Purpose

Global application preferences. Currently: dark mode, expert mode
toggle, voice preset management, default TTS backend selection.

## User journey

1. Open Settings from the sidebar.
2. Toggle dark mode. Applied globally, persists across sessions.
3. Toggle expert mode. Currently unused; reserved for hiding advanced
   controls in future.
4. View and delete user-created voice presets. System presets are
   read-only.
5. Select the default TTS backend (XTTS or Piper). Used when creating
   projects without an explicit backend.

## What it reads

- `app.storage.general` — dark mode, expert mode, default backend
- `bookforge.config.PresetConfig.list_presets()` — user + system presets

## What it writes

- `app.storage.general["dark_mode"]`
- `app.storage.general["expert_mode"]`
- `app.storage.general["default_backend"]`
- Preset files via `PresetConfig.delete_user_preset()`

## What it does NOT do

- **Does not control per-project settings.** Those live in the Wizard
  and Pipeline.
- **Does not manage voices.** That's Voice Box.
- **Does not manage documents.** That's Import & Prepare.

## Open questions

- Expert mode is a stub. It's intended to hide advanced controls from
  casual users, but no controls are currently hidden.
- Consider: project template settings, default preset, default normalize
  target. Not urgent.

## Changelog

- 2026-10-15 — Initial documentation.