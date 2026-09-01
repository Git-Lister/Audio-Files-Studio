
---

# Audio‑Files Studio

*A local, GPU‑accelerated audiobook production studio with voice cloning and full control.*

- **License:** MIT  
- **Python:** 3.11  
- **UI Framework:** NiceGUI 3.16  
- **TTS:** XTTS v2, Piper  

---

## Overview

Audio‑Files Studio (AFD) is a self‑contained, open‑source desktop application that turns plain text into high‑quality audiobooks with **voice cloning**—all running **locally** on your own hardware. No cloud subscriptions, no data sharing, and complete privacy.

Key capabilities:

- **Voice Library** – save, edit, and manage voice presets (your own cloned voices or system voices).  
- **Vocalizer** – fine‑tune voice parameters (temperature, pitch, rate, etc.) with real‑time preview.  
- **Audiobook Pipeline** – process a full text (novel, article, script) into chapter‑by‑chapter audio.  
- **GPU Acceleration** – leverages your NVIDIA GPU (CUDA) for fast synthesis via XTTS v2.  
- **Flexible Backends** – currently supports XTTS (high‑quality cloning) and Piper (lightweight TTS).  
- **Modern UI** – built with NiceGUI, responsive, dark‑mode ready.

---

## Features

### Currently Implemented

| Feature | Description |
|---------|-------------|
| Voice Box (Gallery) | Browse, search, play previews, edit, delete, export/import voice presets. |
| Vocalizer (Creator) | Adjust voice parameters (temperature, length penalty, repetition penalty, top‑p, top‑k, pitch, rate) with live preview generation. |
| Preview Generation | Synthesize a short sample using the current parameters and a reference WAV (for XTTS). |
| Reference Upload | Upload a reference voice WAV to clone a specific speaker. |
| Waveform Display | Visual feedback of the generated preview audio (functional placeholder). |
| Dark Mode | Toggle between light and dark themes. |
| Database Storage | SQLite‑based voice library with CRUD operations and import/export (`.voice.zip`). |
| Docker Support | Ready‑to‑run container with CUDA and all dependencies. |

### Planned / In Development

| Feature | Status |
|---------|--------|
| Radar Chart (Voice Fingerprint) | Design phase (next sprint) |
| Waveform Interactivity (click‑to‑play, zoom, editing) | Planned |
| Project Metadata Table (auto‑track chapters, progress) | Planned |
| Full Audiobook Pipeline (prepare, synthesize, finalize) | Partial (UI skeleton) |
| Setup View Integration (voice library dropdown) | Planned |
| Settings Persistence (default voice, dark mode) | Planned |
| Export/Import UI Polish | Low priority |

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend/UI | NiceGUI (Vue.js + Quasar + Python) |
| TTS Backend | XTTS v2 (Coqui) / Piper TTS |
| Audio Processing | Librosa, SoundFile, Wave |
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
```

Then open your browser at [http://localhost:8501](http://localhost:8501).

> **Note:** Requires NVIDIA Docker runtime and a GPU with CUDA 12.1 support.

### Option 2: Local (Python virtualenv)

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # or `venv\Scripts\activate` on Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Launch the app:
   ```bash
   python -m bookforge.ui.main
   ```

   The UI will be available at `http://localhost:8501`.

---

## Usage Guide

### Voice Box (Gallery)

- **View all voices** – system and user‑created.
- **Search** – filter by name or tags.
- **Play preview** – click the play icon to hear a sample.
- **Edit** – opens the Vocalizer with that voice’s parameters.
- **Delete** – only user‑created voices can be deleted.
- **Export** – save a voice as a `.voice.zip` file.
- **Import** – upload a previously exported `.voice.zip`.

### Vocalizer (Creator)

- **Adjust sliders** – change temperature, pitch, rate, etc.
- **Preview text** – choose from normal, poetic, or scientific samples, or write your own.
- **Upload reference WAV** – provide a sample of the voice you want to clone (for XTTS).
- **Generate Preview** – synthesises the preview text with current settings.
- **Save Voice** – saves the current parameters as a new voice or updates an existing one.
- **Reset** – revert to the loaded voice’s settings or system defaults.

### Audiobook Pipeline (Coming Soon)

- **Prepare** – split your text into chapters and paragraphs.
- **Synthesize** – generate audio for each chunk (parallel processing).
- **Finalize** – export as M4B, MP3, or split files.

---

## Development

### Project Structure

```
Audio-Files-Studio/
├── src/
│   └── bookforge/
│       ├── ui/               # NiceGUI views and components
│       │   ├── main.py       # Entry point, navigation
│       │   ├── state.py      # Global state management
│       │   ├── voice_library.py  # SQLite CRUD + import/export
│       │   └── views/
│       │       ├── home.py
│       │       ├── projects.py
│       │       ├── settings.py
│       │       ├── voice_box.py    # Gallery
│       │       ├── vocalizer.py    # Creator (radar chart coming)
│       │       └── wizard.py
│       ├── tts/              # TTS backends (XTTS, Piper)
│       ├── process/          # Chunking, pipeline logic
│       └── config/           # Preset configurations
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

### Adding a New TTS Backend

1. Implement the backend in `src/bookforge/tts/`.
2. Register it in `factory.py`.
3. Ensure it conforms to the `TTSBackend` interface.

### Contributing

We welcome contributions! Please open an issue or pull request. See our [CONTRIBUTING.md](CONTRIBUTING.md) (if present) for guidelines.

---

## Radar Chart – Coming Next

A **visual voice fingerprint** will be added to the Vocalizer. It will show a 5‑axis radar chart with two‑way binding: sliders control the chart, and dragging the chart vertices updates the sliders. This will provide an intuitive, holistic view of the voice settings.

---

## License

This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.

---

## Acknowledgements

- [Coqui TTS](https://github.com/coqui-ai/TTS) – for XTTS v2.
- [NiceGUI](https://nicegui.io/) – for the beautiful UI framework.
- [Piper TTS](https://github.com/rhasspy/piper) – for lightweight on‑device synthesis.

---

## Contact

For questions, suggestions, or feedback, please open an issue on GitHub or contact the maintainer at [dave@example.com] (placeholder).

---

**Happy audiobook making!**