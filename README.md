# 🎙️ Audio‑Files Studio

> **Local, GPU‑accelerated audiobook creation with XTTS v2 and Piper TTS**

Create high‑quality audiobooks from plain text files using open‑source neural
text‑to‑speech engines. Everything runs on your own machine – no cloud, no
subscriptions, full control.

## ✨ Features

- **Dual TTS backends** – high‑quality XTTS v2 with voice cloning, or fast Piper TTS
- **NiceGUI web interface** – clean, step‑by‑step audiobook creation
- **Resumable projects** – stop and resume long syntheses without losing progress
- **Smart chapter detection** – auto, markdown, structured, and heuristic strategies
- **Incremental processing** – chapter‑by‑chapter synthesis with live progress
- **Audio normalisation** – EBU R128 loudness standardisation
- **Docker‑based** – reproducible CUDA environment for Windows, Linux, and Mac

## 🚀 Quick Start (Docker)

```bash
git clone https://github.com/Git-Lister/Audio-Files-Studio.git
cd Audio-Files-Studio/bookforge

# Build the image
docker-compose build

# Start the studio
docker-compose up
Open http://localhost:8501 and follow the on‑screen wizard.
Note: The first time you use XTTS, the model (~1.9 GB) will be downloaded
and cached inside the models/ directory.
Docker‑free installation (Piper only)
bash
cd bookforge
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev,piper,ui]"
python src/bookforge/ui_nicegui.py
You can then select the Piper backend and use any .onnx voice model placed
in the voices/ folder.
📖 Documentation
Table
Document	Description
bookforge/README.md	Full installation and usage guide (CLI + UI)
CONTRIBUTING.md	Development and testing instructions
🎯 Use Cases
Personal audiobook creation from public domain texts
Academic paper narration
Accessibility aids
Prototyping TTS voice clones
🛠️ Tech Stack
Table
Component	Technology
TTS (quality)	Coqui XTTS v2
TTS (speed)	Piper TTS
UI	NiceGUI
CLI	Typer
Deep learning	PyTorch + CUDA 12.1
Container	Docker Compose (NVIDIA GPU)
Audio	ffmpeg, libsndfile
Text processing	Custom pipeline (cleaner, chunker, sanitizer)
📦 Project Structure
plain
bookforge/
├── books/              ← Input .txt files
├── voices/             ← Piper ONNX models & XTTS reference WAVs
├── out/                ← Output audiobook projects
├── presets/            ← Voice & pacing YAML presets
├── src/bookforge/
│   ├── ui_nicegui.py   ← NiceGUI web interface
│   ├── incremental_processor.py  ← Resumable processing engine
│   ├── tts/            ← Backend factory, Piper & XTTS wrappers
│   ├── audio/          ← Concatenation, normalisation
│   ├── ingest/         ← Text loaders (txt, epub, pdf)
└── tests/              ← Basic test suite
🤝 Contributing
Pull requests welcome! Please read CONTRIBUTING.md
for guidelines on setting up a development environment, running tests, and
submitting changes.
📝 License
MIT License – see LICENSE
🙏 Acknowledgments
Coqui TTS for XTTS v2
Piper TTS for lightweight synthesis
NiceGUI for the web framework