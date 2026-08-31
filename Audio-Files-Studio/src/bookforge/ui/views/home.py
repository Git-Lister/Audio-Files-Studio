# src/bookforge/ui/views/home.py
from nicegui import ui


def view(on_new_project=None):
    container = ui.column().classes("w-full")
    with container:
        ui.label("DEBUG: HOME VIEW").classes("text-h6 text-red")  # Debug label
        ui.label("Welcome to Audio‑Files Studio!").classes("text-h4 q-mb-md")
        ui.markdown("Create high‑quality audiobooks from text files using local TTS models.")
        with ui.row().classes("q-mb-lg"):
            ui.button("✨ Start a New Project", icon="add", on_click=on_new_project).props(
                "color=primary size=lg"
            )
        with ui.card().classes("w-full q-mt-lg"):
            ui.label("How it works").classes("text-h6")
            ui.markdown("""
            1. **Choose a book** – upload a `.txt`, `.epub`, or `.pdf` file.
            2. **Select a voice** – pick a preset or upload a reference WAV for voice cloning.
            3. **Generate the audiobook** – the pipeline will guide you through preparation, synthesis, and finalization.
            """)
        ui.markdown("---")
        ui.markdown("Start by clicking the **New Project** button above or in the sidebar.")
    return container
