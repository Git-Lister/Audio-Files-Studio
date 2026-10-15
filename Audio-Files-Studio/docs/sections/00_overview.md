# Audio-Files-Studio — Overview

**Status:** Active
**Last updated:** 2026-10-15

## What AFS is

A local, GPU-accelerated audiobook production studio. Turns text into
narrated audio using voice cloning, with all processing on-device. No
cloud, no subscriptions, no data leaves the machine.

## Sections in workflow order

The application is designed as a chain of operations, each feeding the
next. This order is not arbitrary — it reflects how a user actually
works, and each section depends on the output of the one before it.

1. **Import & Prepare Text** — turn documents into clean prose
2. **Audio Studio** — clean reference audio and edit outputs *(cross-cutting)*
3. **Voice Box** — browse and manage saved voices
4. **Vocalizer** — create and tune voices
5. **Wizard** — set up a new project
6. **Pipeline** — synthesise the project
7. **Projects** — view, resume, and retrieve outputs
8. **Settings** — global configuration *(cross-cutting)*

**Audio Studio** and **Settings** are cross-cutting: they aren't part of
the linear text-to-audio flow, but they support it at multiple points.

## How sections interact
[Document] ──► Import & Prepare ──► books/*.txt
│
▼
[Reference WAV] ──► Audio Studio ──► clean WAV ──┐
│
▼
Voice Box ◄── Vocalizer
│
▼
[Project name] ──► Wizard ◄─────────────────────┘
│
▼
Pipeline ──► out/<project>/
│
▼
Projects ──► play, resume, re-export


## Principles

Three rules govern how sections evolve:

**1. Reduce, don't add.** If a section duplicates functionality that
lives better elsewhere, remove the duplication. Sections earn their
place by doing something no other section does.

**2. Order of use.** Sections are upgraded in the order the user
encounters them: text first, then voice, then project, then output.

**3. Docs travel with code.** When a section changes, its doc changes
in the same commit. The docs are the shared map.

## What AFS is not

- A general-purpose audio editor (that's a DAW)
- A cloud service
- A text editor
- A voice-conversion tool (it clones, not converts)
- Real-time synthesis

## Key external dependencies

- **XTTS v2 (Coqui)** — primary TTS engine, GPU-accelerated
- **Piper** — lightweight CPU TTS alternative
- **Qwen 2.5 3B Instruct** — local LLM for Smart Cleanup
- **ffmpeg** — audio processing
- **NiceGUI** — web UI framework