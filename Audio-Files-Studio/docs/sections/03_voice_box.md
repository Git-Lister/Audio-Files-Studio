# Section: Voice Box (Gallery)

**Status:** Active
**Last updated:** 2026-10-15

## Purpose

The library of saved voices. Each voice is a saved configuration: a
reference WAV, a set of parameters, a baked preview file, and metadata.
Voice Box is the browsing and management layer; creation happens in
Vocalizer.

## User journey

1. Open Voice Box from the sidebar.
2. Browse voices as cards. Search filters by name or tags.
3. Click play on a card to hear the baked preview.
4. Click Edit to open Vocalizer with that voice loaded.
5. Delete a user-created voice (system voices are read-only).
6. Export a voice as a `.voice.zip`.
7. Import a `.voice.zip` from another instance.

## What it reads

- `voice_library.db` — SQLite, `voices` table
- `user_voices/<id>/reference.wav` — the source of the voice
- `user_voices/<id>/preview.wav` — the baked preview for playback

## What it writes

- `voice_library.db` — on delete
- `user_voices/<id>/` — on delete, removed entirely
- `<export>.zip` — on export, streamed to the browser

## What it does NOT do

- **Does not tune voices.** That's Vocalizer.
- **Does not generate audio.** It plays already-baked previews.
- **Does not sync between machines.** User data is local.
- **Does not allow editing system voices.**

## Key interactions

- **Vocalizer** — sends `edit_voice_id` via `app.storage.general` on Edit.
- **Wizard** — reads from the same DB for the voice dropdown.
- **Audio Studio** — R3 will add "Edit reference" to open in Studio.

## Open questions

- Voices don't sync between machines. Export/import is the current
  workaround. A future "sync folder" concept could be useful but out of
  scope.
- Multi-file upload + Combine exists in Vocalizer but not here. Should
  Voice Box also expose it for reference editing? Probably via Studio.

## Changelog

- 2026-10-15 — Initial documentation.