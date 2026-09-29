# src/bookforge/ui/views/wizard.py
"""New Project Wizard – step‑by‑step setup for book, voice, advanced settings, and confirm."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from nicegui import ui

from bookforge.config import PresetConfig
from bookforge.ui import voice_library as lib
from bookforge.ui.components import extract_upload_bytes, safe_notify, set_processor


def sanitise_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9 _.-]", "_", name)


class WizardState:
    """Holds all state and UI elements for the wizard."""

    def __init__(self, on_switch_to_pipeline=None):
        self.on_switch_to_pipeline = on_switch_to_pipeline
        self.step = 1
        self.step_labels = ["Book", "Voice", "Advanced", "Confirm"]

        # Book
        self.book_event = None
        self.book_path: Path | None = None

        # Voice
        self.backend = "xtts"
        self.speaker_event = None
        self.speaker_wav: Path | None = None
        self.voice_model: Path | None = None
        self.preset_dropdown: ui.select | None = None
        self.speaker_label: ui.label | None = None
        self.selected_voice_id: str | None = None
        self.voice_dropdown: ui.select | None = None
        self.speaker_wavs: list[Path] = []
        self.combine_btn: ui.button | None = None

        # Advanced
        self.temp_slider: ui.slider | None = None
        self.length_slider: ui.slider | None = None
        self.repeat_slider: ui.slider | None = None
        self.normalize_check: ui.checkbox | None = None
        self.target_lufs: ui.number | None = None

        # Confirm
        self.project_name_input: ui.input | None = None

        # Container
        self.step_container: ui.column | None = None
        self.container: ui.column | None = None

    async def load_preset_list(self):
        presets = PresetConfig.list_presets()
        options = [""]
        if presets["system"]:
            options.extend([f"{p} (built‑in)" for p in presets["system"]])
        if presets["user"]:
            options.extend([f"{p} (user)" for p in presets["user"]])
        if self.preset_dropdown:
            self.preset_dropdown.options = options
            if self.preset_dropdown.value and self.preset_dropdown.value not in options:
                self.preset_dropdown.value = ""

    async def apply_preset(self, label: str):
        if not label:
            return
        name = label.split(" (")[0]
        try:
            config = PresetConfig.load(name)
            if config.temperature is not None and self.temp_slider:
                self.temp_slider.value = config.temperature
            if config.length_penalty is not None and self.length_slider:
                self.length_slider.value = config.length_penalty
            if config.repetition_penalty is not None and self.repeat_slider:
                self.repeat_slider.value = config.repetition_penalty
            safe_notify(f"Loaded preset: {name}", type="positive")
        except Exception as e:
            safe_notify(f"Failed to load preset: {e}", type="negative")

    def go_to_step(self, num: int):
        self.step = num
        self.render_step()

    def render_step(self):
        if not self.step_container:
            return
        self.step_container.clear()
        with self.step_container:
            # Larger, bolder step indicator
            with ui.row().classes("w-full items-center gap-4 q-mb-lg"):
                for i, label in enumerate(self.step_labels, 1):
                    color = "primary" if i == self.step else "grey"
                    with ui.element("div").classes(
                        f"q-pa-sm rounded-borders shadow-2 "
                        f"{'bg-primary text-white' if i == self.step else 'bg-grey-3 text-grey-8'}"
                    ):
                        ui.label(f"{i}").classes("text-h6")
                        ui.label(label).classes("text-caption")
                    if i < len(self.step_labels):
                        ui.label("→").classes("text-grey-6")
            # Step content
            if self.step == 1:
                self.render_book_step()
            elif self.step == 2:
                self.render_voice_step()
            elif self.step == 3:
                self.render_advanced_step()
            else:
                self.render_confirm_step()

    # ---- Step 1: Book ----
    def render_book_step(self):
        with ui.column().classes("w-full"):
            ui.label("Select your book").classes("text-h6")
            ui.markdown("Choose a file from the **books/** folder or upload a new one.")
            book_select = ui.select(
                label="Book from books/",
                options=[""] + sorted([p.name for p in Path("books").glob("*.txt") if p.is_file()]),
                value="",
            ).classes("w-full")
            ui.tooltip("Select a .txt file from the books folder")

            preview_area = ui.column().classes("q-mt-md")

            def on_book_upload(e):
                self.book_event = e
                name = (
                    getattr(e.file, "name", "uploaded_book.txt")
                    if hasattr(e, "file")
                    else "uploaded_book.txt"
                )
                safe_notify(f"Book '{name}' uploaded", type="positive")
                asyncio.create_task(self.show_preview(e, preview_area))

            def on_book_select(e):
                value = e.value
                if value:
                    self.book_path = Path("books") / value
                    preview_area.clear()
                    with preview_area:
                        try:
                            if self.book_path:
                                text = self.book_path.read_text(encoding="utf-8", errors="ignore")[
                                    :500
                                ]
                                ui.label("Preview:").classes("text-caption")
                                ui.markdown(f"```\n{text}...\n```").classes("text-caption")
                        except Exception:
                            pass
                else:
                    preview_area.clear()
                    self.book_path = None

            ui.upload(
                label="Or upload a .txt file",
                on_upload=on_book_upload,
            ).classes("w-full")

            book_select.on_value_change(on_book_select)

            with ui.row().classes("q-mt-md"):
                ui.button("Next", on_click=lambda: self.go_to_step(2)).props("color=primary")

    async def show_preview(self, e, preview_area):
        try:
            bytes_data, _ = await extract_upload_bytes(e)
            text = bytes_data.decode("utf-8", errors="ignore")[:500]
            preview_area.clear()
            with preview_area:
                ui.label("Preview:").classes("text-caption")
                ui.markdown(f"```\n{text}...\n```").classes("text-caption")
        except Exception:
            pass

    # ---- Step 2: Voice ----
    def render_voice_step(self):
        with ui.column().classes("w-full"):
            ui.label("Choose your voice").classes("text-h6")
            ui.markdown("Select a preset or upload a reference WAV file.")

            # Preset dropdown
            with ui.row().classes("items-center gap-2"):
                ui.label("Preset").classes("text-caption")
                self.preset_dropdown = ui.select(
                    options=[""],
                    value="",
                ).classes("flex-grow")
                self.preset_dropdown.on_value_change(
                    lambda e: asyncio.create_task(self.apply_preset(e.value))
                )
                ui.button("Refresh", on_click=self.load_preset_list, icon="refresh").props(
                    "flat size=sm"
                )

            # Backend / model selection
            backend_radio = ui.radio(
                ["xtts", "piper"],
                value="xtts",
                on_change=lambda e: setattr(self, "backend", e.value),
            ).props("inline")
            ui.tooltip("XTTS offers high‑quality voice cloning; Piper is fast CPU‑based")

            # Model‑specific options
            model_options = ui.column().classes("w-full")
            with model_options:
                # Piper (hidden by default)
                with ui.column().bind_visibility_from(backend_radio, "value", value="piper"):
                    voice_model_select = ui.select(
                        label="Piper voice model",
                        options=[""]
                        + sorted([p.name for p in Path("voices").glob("*.onnx") if p.is_file()]),
                        value="",
                    ).classes("w-full")
                    voice_model_select.on_value_change(
                        lambda e: setattr(
                            self, "voice_model", Path("voices") / e.value if e.value else None
                        )
                    )

                # XTTS (visible by default)
                with ui.column().bind_visibility_from(backend_radio, "value", value="xtts"):
                    # --- Saved voice dropdown ---
                    voices = lib.list_voices(system=False)
                    voice_options: dict[str, str] = {"": "— Custom upload below —"}
                    for v in voices:
                        voice_options[v["id"]] = v["name"]

                    self.voice_dropdown = ui.select(
                        label="Use a saved voice",
                        options=voice_options,
                        value=self.selected_voice_id or "",
                        on_change=self.on_voice_selected,
                    ).classes("w-full")

                    # --- Reference status label (seeded from state) ---
                    if self.selected_voice_id:
                        v = lib.get_voice(self.selected_voice_id)
                        initial_label = (
                            f"Using saved voice: {v['name']}"
                            if v
                            else "No speaker file selected"
                        )
                    elif self.speaker_wav:
                        initial_label = f"Using uploaded file: {self.speaker_wav.name}"
                    else:
                        initial_label = "No speaker file selected"

                    self.speaker_label = ui.label(initial_label).classes(
                        "text-caption text-grey"
                    )

                    # --- Custom upload (fallback) ---
                    ui.upload(
                        label="Or upload custom reference WAVs (multiple allowed)",
                        on_upload=self.on_speaker_upload,
                        auto_upload=True,
                        multiple=True,
                    ).classes("w-full")

                    # Combine button -- hidden until >1 file is uploaded
                    self.combine_btn = ui.button(
                        "Combine uploaded WAVs", on_click=self.combine_speaker_wavs
                    ).props("flat color=primary")
                    self.combine_btn.visible = len(self.speaker_wavs) > 1

            with ui.row().classes("q-mt-md"):
                ui.button("Back", on_click=lambda: self.go_to_step(1)).props("flat")
                ui.button("Next", on_click=lambda: self.go_to_step(3)).props("color=primary")

    def on_speaker_upload(self, e):
        self.speaker_event = e
        self.selected_voice_id = None
        name = getattr(e.file, "name", "speaker.wav") if hasattr(e, "file") else "speaker.wav"
        if self.speaker_label:
            self.speaker_label.set_text(f"✅ {name}")
        safe_notify(f"Speaker WAV '{name}' uploaded", type="positive")
        asyncio.create_task(self.save_uploaded_speaker(e))

    async def save_uploaded_speaker(self, e):
        try:
            bytes_data, fname = await extract_upload_bytes(e)
            temp_path = Path("temp") / fname
            temp_path.write_bytes(bytes_data)
            self.speaker_wavs.append(temp_path)
            self.speaker_wav = temp_path  # last uploaded is active
            count = len(self.speaker_wavs)
            if self.speaker_label:
                if count == 1:
                    self.speaker_label.set_text(f"Using uploaded file: {temp_path.name}")
                else:
                    self.speaker_label.set_text(
                        f"{count} files uploaded; using: {temp_path.name}"
                    )
            if self.combine_btn is not None:
                try:
                    self.combine_btn.visible = count > 1
                except RuntimeError:
                    pass
        except Exception as e:
            safe_notify(f"Failed to save speaker file: {e}", type="negative")

    async def combine_speaker_wavs(self):
        """Concatenate all uploaded speaker WAVs into one, set as active."""
        if len(self.speaker_wavs) < 2:
            safe_notify("Need at least two WAVs to combine.", type="warning")
            return

        import subprocess

        list_file = Path("temp") / "speaker_concat_list.txt"
        list_file.parent.mkdir(exist_ok=True)
        with open(list_file, "w") as f:
            for wav in self.speaker_wavs:
                f.write(f"file '{wav.absolute()}'\n")

        combined_path = Path("temp") / "combined_speaker.wav"
        try:
            await asyncio.to_thread(
                subprocess.run,
                [
                    "ffmpeg",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(list_file),
                    "-ar",
                    "22050",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(combined_path),
                    "-y",
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as ex:
            safe_notify(
                f"Combine failed: {ex.stderr.decode(errors='ignore')[:200]}",
                type="negative",
            )
            return

        self.speaker_wavs = [combined_path]
        self.speaker_wav = combined_path
        if self.speaker_label:
            self.speaker_label.set_text("Using combined WAV")
        if self.combine_btn is not None:
            try:
                self.combine_btn.visible = False
            except RuntimeError:
                pass
        safe_notify("Combined speaker WAVs into one file.", type="positive")

    def on_voice_selected(self, e):
        """Populate speaker path and slider values from a saved Voice Box entry."""
        voice_id = e.value
        self.selected_voice_id = voice_id or None

        if not voice_id:
            # User chose "Custom upload" -- leave speaker_wav as-is
            if self.speaker_label:
                self.speaker_label.set_text("No speaker file selected")
            return

        voice = lib.get_voice(voice_id)
        if not voice:
            safe_notify(f"Voice {voice_id} not found.", type="negative")
            return

        ref_path = Path(lib.get_voice_dir(voice_id)) / "reference.wav"
        if ref_path.exists():
            self.speaker_wav = ref_path
            if self.speaker_label:
                self.speaker_label.set_text(f"Using saved voice: {voice['name']}")
        else:
            self.speaker_wav = None
            if self.speaker_label:
                self.speaker_label.set_text(
                    f"{voice['name']} has no persistent reference WAV"
                )
            safe_notify(
                f"Voice '{voice['name']}' has no reference WAV on disk. "
                f"Edit and re-save the voice, or upload a custom reference.",
                type="warning",
            )

        # Populate advanced sliders if they exist yet
        if self.temp_slider is not None:
            self.temp_slider.value = voice.get("temperature", 0.667)
        if self.length_slider is not None:
            self.length_slider.value = voice.get("length_penalty", 1.0)
        if self.repeat_slider is not None:
            self.repeat_slider.value = voice.get("repetition_penalty", 5.0)

    # ---- Step 3: Advanced ----
    def render_advanced_step(self):
        with ui.column().classes("w-full"):
            ui.label("Advanced voice settings").classes("text-h6")
            ui.markdown("Adjust these parameters to fine‑tune the voice quality.")

            # Seed slider defaults from selected voice, if any
            default_temp = 0.667
            default_length = 1.0
            default_repeat = 5.0
            if self.selected_voice_id:
                v = lib.get_voice(self.selected_voice_id)
                if v:
                    default_temp = v.get("temperature", default_temp)
                    default_length = v.get("length_penalty", default_length)
                    default_repeat = v.get("repetition_penalty", default_repeat)

            self.temp_slider = ui.slider(
                min=0.1, max=1.0, step=0.01, value=default_temp
            ).classes("w-full")
            ui.label().bind_text_from(
                self.temp_slider, "value", backward=lambda v: f"Temperature: {v:.2f}"
            )

            self.length_slider = ui.slider(
                min=0.5, max=2.0, step=0.05, value=default_length
            ).classes("w-full")
            ui.label().bind_text_from(
                self.length_slider, "value", backward=lambda v: f"Length Penalty: {v:.2f}"
            )

            self.repeat_slider = ui.slider(
                min=1.0, max=10.0, step=0.5, value=default_repeat
            ).classes("w-full")
            ui.label().bind_text_from(
                self.repeat_slider, "value", backward=lambda v: f"Repetition Penalty: {v:.1f}"
            )

            self.normalize_check = ui.checkbox("Normalize final book", value=False)
            self.target_lufs = ui.number(
                label="Target LUFS",
                value=-16.0,
                step=0.5,
                format="%.1f",
            ).bind_visibility_from(self.normalize_check, "value")

            with ui.row().classes("q-mt-md"):
                ui.button("Back", on_click=lambda: self.go_to_step(2)).props("flat")
                ui.button("Next", on_click=lambda: self.go_to_step(4)).props("color=primary")

    # ---- Step 4: Confirm ----
    def render_confirm_step(self):
        with ui.column().classes("w-full"):
            ui.label("Confirm and create project").classes("text-h6")
            ui.markdown("Review your settings and give your project a name.")

            self.project_name_input = ui.input(
                label="Project name",
                value="my-audiobook",
            ).classes("w-full")
            ui.tooltip("This will be the folder name under out/")

            # Summary
            with ui.card().classes("w-full q-mt-md"):
                ui.label("Settings summary").classes("text-subtitle1")
                ui.markdown(
                    f"- **Book**: {self.book_path.name if self.book_path else '(uploaded)'}"
                )
                ui.markdown(f"- **Backend**: {self.backend}")
                if self.backend == "piper":
                    ui.markdown(
                        f"- **Voice model**: {self.voice_model.name if self.voice_model else 'not set'}"
                    )
                else:
                    if self.selected_voice_id:
                        voice = lib.get_voice(self.selected_voice_id)
                        voice_name = voice["name"] if voice else "(unknown)"
                        ui.markdown(f"- **Voice**: {voice_name} (from Voice Box)")
                    else:
                        ui.markdown(
                            f"- **Speaker WAV**: {self.speaker_wav.name if self.speaker_wav else 'not set'}"
                        )
                if self.temp_slider:
                    ui.markdown(f"- **Temperature**: {self.temp_slider.value}")
                if self.length_slider:
                    ui.markdown(f"- **Length Penalty**: {self.length_slider.value}")
                if self.repeat_slider:
                    ui.markdown(f"- **Repetition Penalty**: {self.repeat_slider.value}")
                if self.normalize_check:
                    ui.markdown(f"- **Normalize**: {self.normalize_check.value}")
                    if self.normalize_check.value and self.target_lufs:
                        ui.markdown(f"- **Target LUFS**: {self.target_lufs.value}")

            with ui.row().classes("q-mt-md"):
                ui.button("Back", on_click=lambda: self.go_to_step(3)).props("flat")
                ui.button("Create Project", on_click=self.create_project).props("color=primary")

    # ---- Create Project ----
    async def create_project(self):
        errors = []
        if not self.book_path and not self.book_event:
            errors.append("Please select or upload a book.")
        if self.backend == "xtts" and self.speaker_wav is None:
            errors.append("Please upload a reference speaker WAV for XTTS.")
        if self.backend == "piper" and self.voice_model is None:
            errors.append("Please select a Piper voice model.")
        name = self.project_name_input.value.strip() if self.project_name_input else ""
        if not name:
            errors.append("Please enter a project name.")
        if errors:
            for err in errors:
                safe_notify(err, type="negative")
            return

        if self.book_path is None and self.book_event is not None:
            try:
                book_bytes, book_filename = await extract_upload_bytes(self.book_event)
                self.book_path = Path("temp") / book_filename
                self.book_path.write_bytes(book_bytes)
            except Exception as e:
                safe_notify(f"Failed to save uploaded book: {e}", type="negative")
                return

        if self.book_path is None:
            safe_notify("Book path is missing.", type="negative")
            return

        sanitised = sanitise_filename(name)
        output_dir = Path("out") / sanitised

        xtts_kwargs = {}
        if self.backend == "xtts":
            voice_pitch = 0.0
            voice_rate = 1.0
            if self.selected_voice_id:
                v = lib.get_voice(self.selected_voice_id)
                if v:
                    voice_pitch = v.get("pitch", 0.0)
                    voice_rate = v.get("rate", 1.0)
            xtts_kwargs = {
                "temperature": float(self.temp_slider.value) if self.temp_slider else 0.667,
                "length_penalty": float(self.length_slider.value) if self.length_slider else 1.0,
                "repetition_penalty": float(self.repeat_slider.value) if self.repeat_slider else 5.0,
                "language": "en",
                "pitch": float(voice_pitch),
                "rate": float(voice_rate),
            }

        from bookforge.tts.factory import get_backend

        try:
            tts_backend = await asyncio.to_thread(
                get_backend,
                backend_type=self.backend,
                voice_model=self.voice_model,
                speaker_wav=self.speaker_wav,
                **xtts_kwargs,
            )
        except Exception as e:
            safe_notify(f"Failed to initialise TTS backend: {e}", type="negative")
            return

        from bookforge.incremental_processor import IncrementalProcessor

        proc = IncrementalProcessor(
            input_file=self.book_path,
            output_dir=output_dir,
            backend=tts_backend,
            preset="calm_longform",
            chapter_strategy="auto",
            chapter_min_confidence=0.5,
            normalize=self.normalize_check.value if self.normalize_check else False,
            target_lufs=self.target_lufs.value
            if self.target_lufs and self.normalize_check and self.normalize_check.value
            else -16.0,
            voice_model=self.voice_model,
            speaker_wav=self.speaker_wav,
            backend_params=xtts_kwargs,
        )
        proc.backend_name = self.backend
        set_processor(proc)

        safe_notify(f"Project '{sanitised}' created!", type="positive")
        if self.on_switch_to_pipeline:
            self.on_switch_to_pipeline("prepare")
        else:
            from bookforge.ui import state

            state.set_current_view("pipeline")
            state.set_pipeline_step("prepare")


def view(on_switch_to_pipeline=None):
    container = ui.column().classes("w-full")
    state = WizardState(on_switch_to_pipeline=on_switch_to_pipeline)
    state.container = container
    state.step_container = ui.column().classes("w-full")
    with container:
        state.render_step()
    return container
