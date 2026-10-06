# Audio‑Files Studio

*A local, GPU‑accelerated audiobook production studio with voice cloning,
document preparation, and optional LLM-assisted text cleanup — all running
on your own hardware.*

- **License:** MIT
- **Python:** 3.11
- **UI Framework:** NiceGUI 3.16
- **TTS:** XTTS v2 (default), Piper
- **LLM (optional):** Qwen 2.5 3B Instruct via llama-cpp-python

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Technology Stack](#technology-stack)
4. [Installation](#installation)
5. [Usage Guide](#usage-guide)
6. [Architecture](#architecture)
7. [Project Structure](#project-structure)
8. [Roadmap](#roadmap)
9. [Development](#development)
10. [License](#license)
11. [Acknowledgements](#acknowledgements)

---

## Overview

Audio‑Files Studio (AFD) is a self‑contained, open‑source desktop application
that turns plain text into high‑quality audiobooks with **voice cloning**.
Everything runs locally — no cloud services, no subscriptions, no data leaving
your machine.

The application has three main areas of work:

- **Voice Library** — create, tune, and store cloned voices.
- **Text Preparation** — import documents of various formats, clean them for
  reading aloud, and save them for use in projects.
- **Audiobook Pipeline** — process a full text into chapter-by-chapter audio
  and export as WAV or M4B.

A fourth, optional layer sits on top of text preparation: a small local
language model that can classify ambiguous lines (running headers, metadata,
boilerplate) as part of cleanup. This layer is opt-in and never runs unless
the user chooses it.

---

## Features

### Voice Library

| Feature | Description |
|---------|-------------|
| **Voice Box (Gallery)** | Browse, search, play baked previews, edit, delete, export, import voice presets. |
| **Vocalizer (Creator)** | Fine-tune voice parameters with sliders, presets, and a real-time interactive radar chart. |
| **Reference Upload** | Upload one or more reference WAVs. Optionally combine them into a single richer reference. |
| **Baked Previews** | Each saved voice stores a permanent preview audio file so playback is instant. |
| **Export / Import** | Share voices as `.voice.zip` files that carry reference audio and preview. |

### Text Preparation

| Feature | Description |
|---------|-------------|
| **Multi-Format Extraction** | Import `.txt`, `.md`, `.pdf`, `.docx`, `.epub`, and `.html` documents. |
| **Two-Tier Cleanup** | Cosmetic and structural rules applied as a phased pipeline. Every rule is visible and toggleable. |
| **Phase-Based Pipeline** | Rules run in fixed phases: normalise → strip lines → strip inline → reflow → expand → structure. |
| **Chapter Detection** | Automatic chapter marking for use in the audiobook pipeline. |
| **Editable Review** | Cleaned output is fully editable before saving. |
| **Smart Cleanup (opt-in)** | Local LLM proposes line-level classifications for review. |

### Audiobook Pipeline

| Feature | Description |
|---------|-------------|
| **Prepare** | Chapter and paragraph detection using configurable strategies. |
| **Synthesize** | Chapter-by-chapter synthesis with per-chunk progress, retry, graceful stop, and abort. |
| **Re-synthesize** | Re-synthesize individual chunks without reprocessing the whole book. |
| **Finalize** | Generate `book.wav` and export as M4B with chapter markers. |
| **Download** | Stream final files directly to the browser. |

### Infrastructure

| Feature | Description |
|---------|-------------|
| **GPU Acceleration** | CUDA-accelerated synthesis via XTTS v2. |
| **Docker** | Ready-to-run container with CUDA, ffmpeg, and all dependencies. |
| **Dark Mode** | Global light/dark theme. |
| **SQLite Storage** | Local database for voices and (planned) reports and presets. |
| **Local LLM (optional)** | Qwen 2.5 3B Instruct via llama-cpp-python, loaded lazily on first use. |

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend / UI | NiceGUI (Vue.js + Quasar + Python) |
| TTS Backend | XTTS v2 (Coqui), Piper |
| Local LLM | Qwen 2.5 3B Instruct via llama-cpp-python |
| Document Extraction | pdfminer.six, python-docx, ebooklib, BeautifulSoup4 |
| Audio Processing | ffmpeg, librosa, soundfile |
| Database | SQLite |
| Containerization | Docker + NVIDIA CUDA base image |
| Language | Python 3.11 |

---

## Installation

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/Git-Lister/Audio-Files-Studio.git
cd Audio-Files-Studio
docker compose up --build
Open your browser at http://localhost:8501.

Requirements:

NVIDIA Docker runtime

A GPU with CUDA 12.1 support

~10 GB free disk space (models are cached under /models on first use)

Option 2: Local (Python virtualenv)
Python version: This project requires Python 3.11. The TTS (Coqui)
library does not support Python 3.12+. Install 3.11.x from
python.org.

Windows users: The TTS library requires a C++ compiler. Install the
Microsoft C++ Build Tools
and select the "Desktop development with C++" workload during setup.

Linux / macOS: Docker (Option 1) or WSL2 is recommended to avoid
dependency complexity.

bash
python -m venv venv
source venv/bin/activate    # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
python -m bookforge.ui.main
The UI will be available at http://localhost:8501.

Usage Guide
Voice Box (Gallery)
View all voices — system and user-created.

Search — filter by name or tag.

Play — plays the voice's baked preview.

Edit — opens the Vocalizer with that voice loaded.

Delete — only user-created voices can be deleted.

Export — saves a .voice.zip and streams it to your browser.

Import — restore a previously exported voice.

Vocalizer (Creator)
Quick Start presets — Match Original, Calm Narration, Dramatic Reading.

Voice Character sliders — five sliders driving the radar chart. Labels
above each slider show the current value.

Advanced Sampling sliders — Top-P and Top-K for finer control.

Radar Chart — visually reflects the five character sliders. Vertices are
draggable; dragging updates the corresponding slider.

Reference WAV — upload one or more files. The first is active by default.
Click Combine uploaded to merge them into a single reference.

Generate Preview — synthesise a short sample with the current parameters.

Save Voice — stores the parameters, persists the reference WAV, and bakes
a preview file for later playback.

Import & Prepare Text
Upload — drag or select a document. Supported: .txt, .md, .pdf,
.docx, .epub, .html.

Cleanup options — check or uncheck rules across two tiers. Tooltips
explain each rule.

Re-Clean — re-runs the cleanup with current options.

Reset to extraction — reverts to the raw extracted text.

Review & edit — the middle pane is fully editable. Manual edits are what
gets saved.

Save to books/ — writes the current text to a .txt file in books/
for use in the New Project wizard.

New Project Wizard
Book — select a file from books/ or upload a .txt.

Voice — choose a saved voice from the Voice Box, or upload custom
reference WAVs (multiple allowed, optional Combine).

Advanced — adjust temperature, length penalty, and repetition penalty.
Sliders seed from the chosen voice.

Confirm — review settings, name the project, create it.

Pipeline
Prepare — detect chapters and paragraphs.

Synthesize — process chapter by chapter, or all at once. Per-chunk
progress and re-synthesis available.

Finalize — generate book.wav. Export as M4B with chapter markers.

Settings
Toggle dark mode (single control).

Toggle expert mode.

Manage voice presets.

Set default TTS backend.

Architecture
Layered Pipeline
Text flows through distinct layers, each with a single responsibility:

text
   ┌─────────────────────────────┐
   │  Source document            │  .txt .md .pdf .docx .epub .html
   └──────────────┬──────────────┘
                  │
                  ▼
   ┌─────────────────────────────┐
   │  Extraction                 │  text_extract/extractor.py dispatches
   │                             │  to format-specific extractors
   └──────────────┬──────────────┘
                  │
                  ▼
   ┌─────────────────────────────┐
   │  Deterministic Cleanup      │  text_extract/cleanup.py runs rules
   │  (phased)                   │  in fixed phase order
   └──────────────┬──────────────┘
                  │
                  ▼
   ┌─────────────────────────────┐
   │  Optional LLM Executor      │  llm/executor.py proposes line-level
   │  (opt-in, user-reviewed)    │  classifications; user accepts/rejects
   └──────────────┬──────────────┘
                  │
                  ▼
   ┌─────────────────────────────┐
   │  Save to books/             │  Editable .txt
   └─────────────────────────────┘
Cleanup Phases
Every rule belongs to a phase. Phases run in fixed order; within a phase,
rule order is neutral by contract.

Phase	Purpose
normalise	Canonicalise form (unicode, line endings, whitespace).
strip_lines	Remove whole lines matching patterns (running headers, page numbers).
strip_inline	Remove in-line patterns (URLs, emails, footnote markers).
reflow	Join wrapped lines; collapse internal whitespace.
expand	Substitute known abbreviations.
structure	Add chapter/section markers.
Project Structure
text
Audio-Files-Studio/
├── src/
│   └── bookforge/
│       ├── ui/                       # NiceGUI views and components
│       │   ├── main.py               # Entry point, navigation
│       │   ├── state.py              # Global state
│       │   ├── components.py         # Notifications, shared widgets
│       │   ├── voice_library.py      # Voice DB and file management
│       │   └── views/
│       │       ├── home.py
│       │       ├── projects.py
│       │       ├── settings.py
│       │       ├── voice_box.py      # Gallery
│       │       ├── vocalizer.py      # Creator + Radar Chart
│       │       ├── wizard.py         # New Project wizard
│       │       ├── pipeline.py       # Prepare / Synthesize / Finalize
│       │       └── import_prepare.py # Import & Prepare Text
│       ├── tts/                      # TTS backends
│       │   ├── backend.py            # Base interface
│       │   ├── factory.py            # Dispatch
│       │   ├── xtts.py               # XTTS v2 backend
│       │   └── piper.py              # Piper backend
│       ├── text_extract/             # Document extraction and cleanup
│       │   ├── extractor.py          # Format dispatch
│       │   ├── pdf_extract.py
│       │   ├── docx_extract.py
│       │   ├── epub_extract.py
│       │   ├── html_extract.py
│       │   ├── txt_extract.py
│       │   ├── cleanup.py            # Phase-based rules
│       │   └── errors.py
│       ├── llm/                      # Optional local LLM
│       │   ├── engine.py             # Model loading, caching
│       │   ├── executor.py           # Line classification
│       │   ├── prompts.py
│       │   ├── schemas.py
│       │   └── __main__.py           # CLI verification
│       ├── process/                  # Text processing
│       │   ├── chunker.py
│       │   ├── cleaner.py
│       │   ├── sanitize.py
│       │   └── chapter_detector.py
│       ├── ingest/                   # Book ingestion
│       │   └── txt_ingest.py
│       ├── audio/                    # Audio utilities
│       │   ├── concat.py
│       │   └── normalise.py
│       ├── config/                   # Preset configuration
│       └── incremental_processor.py  # Pipeline orchestration
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
Roadmap
Current
Voice Library — complete.

Vocalizer — complete; radar chart fully interactive.

Text Preparation — complete; multi-format extraction and phase-based cleanup.

Audiobook Pipeline — complete; M4B export working.

LLM Infrastructure — model loading, structured output, CLI verification.

Next
Stage 2b — LLM UI Integration. Button in Import & Prepare to run smart
cleanup. Diff view of proposed changes. Accept/reject per suggestion.

Stage 2c — Reports Persistence. Save every LLM run for later analysis.

Planned
Stage 3 — Reports Storage. SQLite-backed store with full-text search.

Stage 4 — Observer Tool. A witness for LLM-assisted runs, producing
reports for later analysis.

Stage 5 — Text Presets. Named configurations bundling cleanup rules,
prompts, and evaluation criteria. Modelled on Voice Box.

Stage 6 — Analyser Tool. Cross-report meta-analysis to find patterns
and propose preset adjustments.

Stage 7 — Medieval Preset. A domain-specific text transformation as the
first exercise of the full framework.

Polish (Backlog)
Waveform interactivity (click-to-seek, playhead).

Tooltips on the remaining Vocalizer sliders.

Rules to strip or condense References sections.

Chapter detector: reduce false positives on academic author blocks.

Project metadata table.

Wizard: link from Book step to Import & Prepare.

Settings persistence across sessions.

Development
Adding a Cleanup Rule
Write a pure str -> str function in text_extract/cleanup.py.

Decide which phase it belongs to. See the phase table above.

Add a CleanupRule entry to ALL_RULES.

Add its key to the appropriate phase in PHASES.

_validate_phases() runs at import; the pipeline will fail loudly if a
rule is unassigned or double-assigned.

Add a tooltip in the rule's description.

Adding a TTS Backend
Implement the backend in src/bookforge/tts/.

Register it in factory.py and add its parameters to the allowlist.

Ensure it conforms to the TTSBackend interface
(synthesize_chunk(chunk, config, out_path)).

Adding a Document Format
Write an extract(path: Path) -> str function in text_extract/.

Add the extension to _EXTRACTORS in extractor.py and to
SUPPORTED_EXTENSIONS.

The import UI picks it up automatically.

Working With the LLM Layer
The llm/ package is standalone. Verify it works with:

bash
docker compose run --rm studio python -m bookforge.llm
First run downloads the model (~2 GB) to the container's persistent /models
volume. Subsequent runs load from cache.

Contributing
Issues and pull requests are welcome on GitHub.

License
This project is licensed under the MIT License — see the LICENSE
file for details.

Acknowledgements
Coqui TTS — XTTS v2 for voice cloning.

NiceGUI — Python-native web UI framework.

Piper TTS — lightweight on-device synthesis.

llama-cpp-python — local LLM inference.

Qwen 2.5 — open instruction-tuned model.

pdfminer.six, python-docx, ebooklib, BeautifulSoup — document extraction.

ffmpeg — audio processing.

