Here is the fully updated `README.md`. It reflects the massive architectural leap we've made: the multi-engine TTS system (F5-TTS, StyleTTS2), the complete Audio Studio (with recording, editing, and export), the LLM-powered Smart Cleanup, and the new single-form Wizard. 

I've removed the emojis to keep it professional and strictly documented the new architecture, dependencies, and usage flows.

---

# Audio-Files Studio

*A local, GPU-accelerated audiobook production studio with multi-engine voice cloning, document preparation, and optional LLM-assisted text cleanup.*

- **License:** MIT
- **Python:** 3.11
- **UI Framework:** NiceGUI 3.16
- **TTS Engines:** XTTS v2 (Legacy), F5-TTS (Speed), StyleTTS2 (Artistry)
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

Audio-Files Studio (AFD) is a self-contained, open-source desktop application that turns plain text into high-quality audiobooks with **voice cloning**. Everything runs locally — no cloud services, no subscriptions, no data leaving your machine.

The application has four main areas of work:

- **Voice Library** — create, tune, and store cloned voices.
- **Text Preparation** — import documents of various formats, clean them for reading aloud (with LLM assistance), and save them for use in projects.
- **Audio Studio** — a dedicated workspace for cleaning up reference audio, trimming silence, adjusting loudness, and editing generated book outputs.
- **Audiobook Pipeline** — process a full text into chapter-by-chapter audio and export as WAV or M4B.

A fourth, optional layer sits on top of text preparation: a small local language model that can classify ambiguous lines (running headers, metadata, boilerplate) as part of cleanup. This layer is opt-in and runs entirely on your local GPU.

---

## Features

### Voice Library & Vocalizer

| Feature | Description |
|---------|-------------|
| **Multi-Engine Support** | Choose between **XTTS v2** (Legacy Cloning), **F5-TTS** (Fast, Stable Drafting), or **StyleTTS2** (Human-Level Artistry & Accent Retention). |
| **Voice Box (Gallery)** | Browse, search, play baked previews, edit, delete, export, and import voice presets. |
| **Vocalizer (Creator)** | Fine-tune voice parameters with sliders, presets, and a real-time interactive radar chart. Sliders automatically disable for engines that don't use them (like F5). |
| **Reference Audio** | Upload one or more reference WAVs. Optionally combine them into a single richer reference. |
| **Baked Previews** | Each saved voice stores a permanent preview audio file so playback is instant in the Gallery. |

### Audio Studio

| Feature | Description |
|---------|-------------|
| **Waveform Editing** | Load any audio file, visualize the waveform, drag to select regions, and trim or delete with undo/redo support. |
| **Polish Operations** | Normalize loudness (EBU R128), auto-trim silences, and apply fade-in/fade-out effects. |
| **Format Conversion** | Export edited audio as WAV, MP3, or FLAC. |
| **Save to Voice Box** | Instantly save a cleaned audio clip as a new reference voice in the Gallery. |

### Text Preparation (Import & Prepare)

| Feature | Description |
|---------|-------------|
| **Multi-Format Extraction** | Import `.txt`, `.md`, `.pdf`, `.docx`, `.epub`, and `.html` documents. |
| **Phased Cleanup Pipeline** | Deterministic rules applied in phases: normalise → strip lines → strip inline → reflow → expand → structure. |
| **Document Context** | Select "Academic", "Fiction", or "Script" to automatically tune the LLM to strip the correct types of metadata. |
| **Smart Cleanup (LLM)** | Local LLM proposes line-level classifications (keep, remove, heading, uncertain) for review. |
| **Editable Review** | Cleaned output is fully editable. Toggle between original extraction and cleaned text before saving. |

### Audiobook Pipeline & Projects

| Feature | Description |
|---------|-------------|
| **Wizard** | A single-form setup screen to select a book, choose a voice, and name the project. |
| **Prepare** | Chapter and paragraph detection using configurable strategies. |
| **Synthesize** | Chapter-by-chapter synthesis with per-chunk progress, retry, pause/resume, and abort. |
| **Re-synthesize** | Re-synthesize individual chunks or chapters without reprocessing the whole book. |
| **Finalize** | Generate `book.wav` and export as M4B with chapter markers. |
| **Projects View** | A three-state dashboard (In Progress, Completed, Empty) to resume work, play finished books, or delete old projects. |

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend / UI | NiceGUI (Vue.js + Quasar + Python) |
| TTS Backends | XTTS v2 (Coqui), F5-TTS, StyleTTS2 |
| Local LLM | Qwen 2.5 3B Instruct via llama-cpp-python |
| Document Extraction | pdfminer.six, python-docx, ebooklib, BeautifulSoup4 |
| Audio Processing | ffmpeg, librosa, soundfile, pydub |
| Database | SQLite |
| Containerization | Docker + NVIDIA CUDA base image (devel) |
| Language | Python 3.11 |

---

## Installation

### Option 1: Docker (Recommended)

This project uses a multi-stage Docker build to keep rebuilds fast. The base image handles PyTorch and CUDA, while `Dockerfile.phase3` installs the TTS engines.

```bash
git clone https://github.com/Git-Lister/Audio-Files-Studio.git
cd Audio-Files-Studio
docker compose build
docker compose up
```

Open your browser at [http://localhost:8501](http://localhost:8501).

**Requirements:**
- NVIDIA Docker runtime
- A GPU with CUDA 12.1 support
- ~15 GB free disk space (models are cached under `/models` and `/root/.cache/huggingface` on first use)

*Note: If you have a corporate firewall (e.g., Kaspersky) intercepting SSL, ensure the environment variables `HF_HUB_DISABLE_SSL_VERIFY=1` and `PYTHONHTTPSVERIFY=0` are set in your `docker-compose.yml`.*

### Option 2: Local (Python virtualenv)

> **Python version:** This project requires **Python 3.11**. The `TTS` (Coqui) library does not support Python 3.12+.

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the app:
   ```bash
   python -m bookforge.ui.main
   ```

---

## Usage Guide

### Vocalizer (Creator)
- **Engine Selector:** Choose **XTTS** for legacy voice cloning, **F5-TTS** for fast and stable generation, or **StyleTTS2** for maximum human-level quality and accent retention.
- **Voice Character sliders:** Five sliders driving the radar chart. (Note: F5 and StyleTTS2 ignore these, so the sliders will gray out).
- **Reference WAV:** Upload one or more files. Click *Combine uploaded* to merge them.
- **Generate Preview:** Synthesise a short sample with the current engine and parameters.
- **Save Voice:** Stores the parameters, engine type, persists the reference WAV, and bakes a preview file.

### Audio Studio
- **Upload** a rough voice note or generated output.
- **Trim/Delete:** Drag on the waveform to select a region, then click Trim or Delete.
- **Normalize:** Click "Normalize Volume" to bring the audio to a standard broadcast loudness (-16 LUFS).
- **Trim Silence:** Removes long gaps and dead air automatically.
- **Save to Voice Box:** If you just cleaned up a perfect 30-second sample of a voice, click this to instantly add it to the Gallery as a new VoiceProfile.

### Import & Prepare Text
- **Upload** a document.
- **Document Type:** Select "Academic", "Fiction", or "Script" to prime the LLM.
- **Smart Cleanup:** Click the button to have the local LLM scan the text for running headers, page numbers, or boilerplate. Review its proposals in the modal before applying.
- **Save to books/:** Saves the cleaned `.txt` file for use in the Wizard.

### Wizard & Pipeline
1. **Wizard:** Select a `.txt` file from `books/`, pick a voice from the Voice Box, and click "Create Project".
2. **Prepare:** Detect chapters and paragraphs.
3. **Synthesize:** Process the book. You can pause and resume. The UI shows which engine is currently generating.
4. **Finalize:** Generate `book.wav` and export as M4B with chapter markers.

---

## Architecture

### Layered Pipeline
Text flows through distinct layers, each with a single responsibility:

```
   [Source Document]
          │
          ▼
   [Extraction] ──► PDF/DOCX/EPUB/HTML parsers
          │
          ▼
   [Deterministic Cleanup] ──► Phased rules (Normalise, Strip, Reflow)
          │
          ▼
   [Optional LLM Executor] ──► Line classification (Keep/Remove)
          │
          ▼
   [Save to books/] ──► Editable .txt
```

### TTS Abstraction Layer
The `VoiceProfile` dataclass and `TTSBackend` interface decouple the voice definition from the engine.
- `VoiceProfile`: Stores the engine type, reference WAV, and generation parameters.
- `TTSBackend`: An ABC implemented by `XTTSBackend`, `F5Backend`, and `StyleTTS2Backend`.
- `factory.py`: Reads the `VoiceProfile.backend_type` and instantiates the correct engine.

---

## Project Structure

```
Audio-Files-Studio/
├── src/
│   └── bookforge/
│       ├── ui/                       # NiceGUI views and components
│       │   ├── main.py               # Entry point, navigation
│       │   ├── state.py              # Global state
│       │   ├── voice_library.py      # Voice DB and file management
│       │   └── views/
│       │       ├── voice_box.py      # Gallery
│       │       ├── vocalizer.py      # Creator + Radar Chart
│       │       ├── audio_studio.py   # Waveform editor
│       │       ├── wizard.py         # Single-form project setup
│       │       ├── pipeline.py       # Prepare / Synthesize / Finalize
│       │       └── import_prepare.py # Text extraction and cleanup
│       ├── tts/                      # TTS backends
│       │   ├── backend.py            # Base ABC
│       │   ├── factory.py            # Dispatch based on VoiceProfile
│       │   ├── xtts.py               # XTTS v2 backend
│       │   ├── f5.py                 # F5-TTS backend
│       │   └── styletts2.py          # StyleTTS2 backend
│       ├── llm/                      # Optional local LLM
│       │   ├── engine.py             # Model loading (llama-cpp-python)
│       │   ├── executor.py           # Line classification
│       │   └── reports.py            # SQLite persistence of LLM runs
│       ├── text_extract/             # Document extraction and cleanup
│       ├── audio/                    # Audio utilities
│       │   ├── concat.py             # FFmpeg concat with format normalization
│       │   ├── editor.py             # Trim, fade, normalize operations
│       │   └── peaks.py              # Waveform generation
│       └── incremental_processor.py  # Pipeline orchestration
├── Dockerfile
├── Dockerfile.phase3                 # Installs F5-TTS, StyleTTS2, OpenVoice
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Roadmap

### Current (Completed)
- Voice Library and Vocalizer with XTTS, F5-TTS, and StyleTTS2.
- Audio Studio R1 and R2 (Waveform, Trim, Normalize, Fades, Export).
- Import & Prepare with LLM Smart Cleanup (Context-aware).
- Single-form Wizard and Three-state Projects dashboard.

### Next
- **Batch AG: Draft & Refine Workflow.** Implement a hybrid pipeline where F5-TTS generates the initial draft, and specific chunks can be flagged for "Refinement" using StyleTTS2.
- **In-Browser Recording.** Add a microphone recording widget to Audio Studio and Vocalizer to capture perfect reference samples on the fly.

### Planned
- **Phase 4: On-Device Engine.** Integrate NeuTTS (GGUF) or Kokoro-82M for CPU-only or low-VRAM environments.
- **Timbre Modulation.** Add pitch and formant shifting to Audio Studio so users can tweak the character of a voice post-generation.

---

## Development

### Adding a TTS Backend
1. Implement a class in `src/bookforge/tts/` that inherits from `TTSBackend` (requires `load_model`, `synthesize_chunk`, and `unload`).
2. Add the routing logic to `factory.py`.
3. Add the engine name to the `VoiceProfile.backend_type` comment and the `vocalizer.py` dropdown.

### Contributing
Issues and pull requests are welcome on GitHub.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## Acknowledgements

- [Coqui TTS](https://github.com/coqui-ai/TTS) — XTTS v2 for legacy voice cloning.
- [F5-TTS](https://github.com/SWivid/F5-TTS) — Fast, non-autoregressive TTS.
- [StyleTTS2](https://github.com/yl4579/StyleTTS2) — Human-level prosody and style.
- [NiceGUI](https://nicegui.io/) — Python-native web UI framework.
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) — Local LLM inference.
- [Qwen 2.5](https://huggingface.co/Qwen) — Open instruction-tuned model.
- [ffmpeg](https://ffmpeg.org/) — Audio processing.