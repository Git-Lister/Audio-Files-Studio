# Section: Vocalizer (Creator)

**Status:** Active
**Last updated:** 2026-10-15

## Purpose

The voice creation and tuning interface. Sliders for character
parameters (temperature, length penalty, repetition penalty, pitch,
rate), advanced sampling controls (top-p, top-k), a live radar chart,
reference upload, preview generation, and save.

The Vocalizer is where voices are *made*. Voice Box stores and plays
them. Wizard references them. Pipeline uses them.

## User journey

1. Open Vocalizer from the sidebar, or click Edit on a Voice Box card.
2. Enter a voice name, description, and tags.
3. Adjust the five character sliders. The radar chart updates live.
4. Optionally adjust top-p and top-k for fine-grained control.
5. Upload a reference WAV (multiple allowed, combine optional).
6. Type preview text, or pick from Normal / Poetic / Scientific.
7. Click Generate Preview. Listen, adjust, repeat.
8. Click Save Voice. The parameters are stored, the reference is
   persisted to `user_voices/<id>/`, and a baked preview is generated.

## What it reads

- `voice_library.db` — when loading a voice via Edit
- `user_voices/<id>/reference.wav` — when reloading a saved voice
- Reference uploads — via the browser

## What it writes

- `voice_library.db` — voice parameters and metadata
- `user_voices/<id>/reference.wav` — the persistent reference
- `user_voices/<id>/preview.wav` — the baked preview
- `temp/preview_*.wav` — preview generations before saving
- `reports.db` — N/A (that's Smart Cleanup)
- `app.storage.general["edit_voice_id"]` — cleared on load

## What it does NOT do

- **Does not manage the voice library.** That's Voice Box.
- **Does not synthesise longform.** Only short previews.
- **Does not edit audio waveforms.** That's Audio Studio. Currently
  reference uploads are accepted as-is; R3 will link to Studio.

## Key interactions

- **Voice Box** — receives `edit_voice_id` on load. Sends users back
  via "Discard Changes" or after Save.
- **Wizard** — voices saved here appear in the wizard's dropdown.
- **Audio Studio** — R3 will add a link to open the current reference
  in Studio for cleaning.

## Open questions

- Reference audio quality drives output quality. A direct link to Audio
  Studio would let users clean recordings without leaving the flow.
- The radar chart shows the parameters. A future enhancement: compare
  two voices side-by-side on the same chart.

## Changelog

- 2026-10-15 — Initial documentation.