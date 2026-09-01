# src/bookforge/ui/views/vocalizer.py
"""Vocalizer – voice editor with sliders, preview, and waveform."""

from __future__ import annotations

import asyncio
import struct
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from nicegui import ui

from bookforge.ui import voice_library as lib
from bookforge.ui.components import safe_notify

DEFAULT_PREVIEW = "This is a sample of my voice. It is clear, natural, and ready for narration."
POETIC_PREVIEW = "In th’ olde dayes of the King Arthour, Of which that Britons speken greet honour, All was this land fulfild of fayerye."
SCIENTIFIC_PREVIEW = "The quantum entanglement of the phonon field underlies the emergent properties of the vocal tract's resonance, which we model as a coupled oscillator system."


def view():
    container = ui.column().classes("w-full")

    # ---- State ----
    voice_id = None
    uploaded_ref_path: Optional[Path] = None

    # ---- UI controls (populated later) ----
    name_input = None
    desc_input = None
    tags_input = None
    preview_textarea = None
    temp_slider = length_slider = repeat_slider = None
    pitch_slider = rate_slider = top_p_slider = top_k_slider = None
    normalize_check = None
    ref_status = None
    generate_btn = None
    preview_spinner = None
    audio_player = None

    # ---- Helper functions (defined before UI) ----
    def set_preview_text(text):
        if preview_textarea is not None:
            preview_textarea.value = text

    def set_sliders_from_voice(voice):
        temp_slider.value = voice.get("temperature", 0.667)
        length_slider.value = voice.get("length_penalty", 1.0)
        repeat_slider.value = voice.get("repetition_penalty", 5.0)
        top_p_slider.value = voice.get("top_p", 0.8)
        top_k_slider.value = voice.get("top_k", 50)
        pitch_slider.value = voice.get("pitch", 0.0)
        rate_slider.value = voice.get("rate", 1.0)
        normalize_check.value = bool(voice.get("normalize", False))
        name_input.value = voice.get("name", "My Voice")
        desc_input.value = voice.get("description", "")
        tags_input.value = voice.get("tags", "")
        preview_textarea.value = voice.get("preview_text", DEFAULT_PREVIEW)
        ref_path = voice.get("reference_wav_path")
        if ref_path and Path(ref_path).exists():
            ref_status.set_text(f"Reference: {Path(ref_path).name}")
        else:
            ref_status.set_text("No reference uploaded")

    def get_current_params():
        return {
            "temperature": temp_slider.value,
            "length_penalty": length_slider.value,
            "repetition_penalty": repeat_slider.value,
            "top_p": top_p_slider.value,
            "top_k": int(top_k_slider.value or 0),
            "pitch": pitch_slider.value,
            "rate": rate_slider.value,
            "normalize": normalize_check.value,
            "language": "en",
            "preset_name": "calm_longform",
        }

    def reset_to_loaded():
        if voice_id:
            voice = lib.get_voice(voice_id)
            if voice:
                set_sliders_from_voice(voice)
                safe_notify("Reset to loaded voice parameters.", type="info")
        else:
            safe_notify("No voice loaded.", type="warning")

    def reset_to_system_defaults():
        default_voice = {
            "temperature": 0.667,
            "length_penalty": 1.0,
            "repetition_penalty": 5.0,
            "top_p": 0.8,
            "top_k": 50,
            "pitch": 0.0,
            "rate": 1.0,
            "normalize": False,
        }
        set_sliders_from_voice(default_voice)
        safe_notify("Reset to system defaults.", type="info")

    async def generate_preview_action():
        preview_spinner.visible = True
        generate_btn.disable()
        try:
            text = preview_textarea.value or DEFAULT_PREVIEW
            params = get_current_params()
            # Use uploaded if available, else saved voice reference
            ref_path_to_use = uploaded_ref_path
            if ref_path_to_use is None and voice_id:
                voice = lib.get_voice(voice_id)
                if voice and voice.get("reference_wav_path"):
                    ref_path_to_use = Path(voice["reference_wav_path"])
            # Debug: print the path
            print(f"🔊 Using reference WAV: {ref_path_to_use}")
            wav_path = await generate_preview(text, params, ref_path_to_use)
            audio_player.set_source(str(wav_path))
            draw_waveform(wav_path)
            safe_notify("Preview generated!", type="positive")
        except Exception as e:
            safe_notify(f"Generation failed: {e}", type="negative")
        finally:
            preview_spinner.visible = False
            generate_btn.enable()

    def draw_waveform(wav_path):
        try:
            with wave.open(str(wav_path), "rb") as wav:
                nchannels, sampwidth, nframes, _, _, _ = wav.getparams()
                frames = wav.readframes(nframes)
                if sampwidth == 2:
                    samples = struct.unpack(f"{nframes * nchannels}h", frames)
                else:
                    samples = [0] * nframes
                if nchannels == 2:
                    samples = samples[::2]
                max_points = 600
                step = max(1, len(samples) // max_points)
                downsampled = samples[::step]
                max_val = max(abs(min(downsampled)), abs(max(downsampled)))
                normalized = (
                    [v / max_val for v in downsampled] if max_val > 0 else [0] * len(downsampled)
                )
                js = f"""
                var canvas = document.getElementById('waveformCanvas');
                if (!canvas) return;
                var ctx = canvas.getContext('2d');
                var w = canvas.width;
                var h = canvas.height;
                ctx.clearRect(0, 0, w, h);
                ctx.strokeStyle = '#4CAF50';
                ctx.lineWidth = 2;
                ctx.beginPath();
                var data = {normalized};
                var mid = h/2;
                var step = w / data.length;
                for (var i = 0; i < data.length; i++) {{
                    var x = i * step;
                    var y = mid - data[i] * mid;
                    if (i === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }}
                ctx.stroke();
                """
                ui.run_javascript(js)
        except Exception:
            ui.run_javascript("""
            var canvas = document.getElementById('waveformCanvas');
            if (!canvas) return;
            var ctx = canvas.getContext('2d');
            var w = canvas.width;
            var h = canvas.height;
            ctx.clearRect(0, 0, w, h);
            ctx.strokeStyle = '#4CAF50';
            ctx.lineWidth = 2;
            ctx.beginPath();
            var mid = h/2;
            for (var i = 0; i < 600; i++) {
                var x = i * (w / 600);
                var y = mid - Math.sin(i * 0.1) * mid * 0.8;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
            """)

    async def save_voice():
        data = {
            "name": (name_input.value or "").strip() or "Unnamed Voice",
            "description": desc_input.value or "",
            "tags": tags_input.value or "",
            "preview_text": preview_textarea.value or DEFAULT_PREVIEW,
            **get_current_params(),
            "reference_wav_path": str(uploaded_ref_path) if uploaded_ref_path else None,
        }
        if voice_id:
            lib.update_voice(voice_id, data)
            safe_notify(f"Voice '{data['name']}' updated!", type="positive")
        else:
            new_id = lib.add_voice(data)
            safe_notify(f"Voice '{data['name']}' created!", type="positive")
        navigate_back()

    def navigate_back():
        if hasattr(container, "switch_to_gallery") and container.switch_to_gallery:
            container.switch_to_gallery()
        else:
            safe_notify("Return to Gallery not configured.", type="warning")

    # ---- Upload handler (async) ----
    async def handle_upload(e):
        nonlocal uploaded_ref_path
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        unique_name = f"ref_{uuid.uuid4().hex[:8]}.wav"
        ref_path = temp_dir / unique_name
        content = await e.file.read()  # await the coroutine
        with open(ref_path, "wb") as f:
            f.write(content)
        uploaded_ref_path = ref_path
        ref_status.set_text(f"Reference: {e.file.name} (uploaded)")
        safe_notify("Reference WAV uploaded.", type="positive")
        print(f"📁 Uploaded reference to: {ref_path}")

    # ---- Build UI (after helper functions) ----
    with container:
        ui.label("🎤 Vocalizer").classes("text-h5 q-mb-md")
        ui.markdown(
            "Create and edit voices. Adjust sliders, see the radar chart, and preview the sound."
        )

        name_input = ui.input(label="Voice name", value="My Voice").classes("w-full")
        desc_input = ui.input(label="Description", value="").classes("w-full")
        tags_input = ui.input(label="Tags (comma separated)", value="").classes("w-full")
        preview_textarea = (
            ui.textarea(label="Preview text", value=DEFAULT_PREVIEW)
            .props("rows=3")
            .classes("w-full")
        )

        with ui.row().classes("w-full"):
            with ui.column().classes("w-1/3 q-pr-md"):
                ui.label("Voice").classes("text-h6")
                temp_slider = ui.slider(min=0.1, max=1.0, step=0.01, value=0.667).classes("w-full")
                ui.label().bind_text_from(
                    temp_slider, "value", backward=lambda v: f"Temperature: {v:.2f}"
                )

                length_slider = ui.slider(min=0.5, max=2.0, step=0.05, value=1.0).classes("w-full")
                ui.label().bind_text_from(
                    length_slider, "value", backward=lambda v: f"Length Penalty: {v:.2f}"
                )

                repeat_slider = ui.slider(min=1.0, max=10.0, step=0.5, value=5.0).classes("w-full")
                ui.label().bind_text_from(
                    repeat_slider, "value", backward=lambda v: f"Repetition Penalty: {v:.1f}"
                )

                ui.label("Pacing").classes("text-h6 q-mt-md")
                pitch_slider = ui.slider(min=-5, max=5, step=0.5, value=0).classes("w-full")
                ui.label().bind_text_from(
                    pitch_slider, "value", backward=lambda v: f"Pitch: {v:.1f}"
                )

                rate_slider = ui.slider(min=0.5, max=2.0, step=0.05, value=1.0).classes("w-full")
                ui.label().bind_text_from(rate_slider, "value", backward=lambda v: f"Rate: {v:.2f}")

                ui.label("Clarity").classes("text-h6 q-mt-md")
                top_p_slider = ui.slider(min=0.0, max=1.0, step=0.01, value=0.8).classes("w-full")
                ui.label().bind_text_from(
                    top_p_slider, "value", backward=lambda v: f"Top‑P: {v:.2f}"
                )

                top_k_slider = ui.slider(min=0, max=100, step=1, value=50).classes("w-full")
                ui.label().bind_text_from(
                    top_k_slider, "value", backward=lambda v: f"Top‑K: {int(v)}"
                )

                normalize_check = ui.checkbox("Normalize volume", value=False)

                ui.label("Reference WAV").classes("text-h6 q-mt-md")
                ui.upload(
                    label="Upload reference WAV", auto_upload=True, on_upload=handle_upload
                ).classes("w-full")
                ref_status = ui.label("No reference uploaded").classes("text-caption text-grey")

            with ui.column().classes("w-2/3"):
                with ui.card().classes("w-full q-mb-md"):
                    ui.label("Radar Chart").classes("text-h6")
                    ui.markdown("(Interactive chart will appear here in a later update.)")
                    ui.html(
                        "<div style='height:300px; background:#f0f0f0; display:flex; align-items:center; justify-content:center;'>Radar Chart Coming Soon</div>"
                    )

                with ui.card().classes("w-full"):
                    ui.label("Preview").classes("text-h6")
                    with ui.row().classes("items-center gap-2"):
                        ui.button(
                            "Normal", on_click=lambda: set_preview_text(DEFAULT_PREVIEW)
                        ).props("flat")
                        ui.button(
                            "Poetic", on_click=lambda: set_preview_text(POETIC_PREVIEW)
                        ).props("flat")
                        ui.button(
                            "Scientific", on_click=lambda: set_preview_text(SCIENTIFIC_PREVIEW)
                        ).props("flat")
                    generate_btn = ui.button(
                        "Generate Preview", on_click=generate_preview_action
                    ).props("color=primary")
                    preview_spinner = ui.spinner(size="md").props("color=primary")
                    preview_spinner.visible = False
                    audio_player = ui.audio("").classes("w-full q-mt-sm")
                    ui.html(
                        "<canvas id='waveformCanvas' width='600' height='100' style='width:100%; height:100px; background:#f8f8f8;'></canvas>"
                    )

                with ui.row().classes("q-mt-md"):
                    ui.button("Save Voice", on_click=save_voice).props("color=positive")
                    ui.button("Discard Changes", on_click=navigate_back).props("flat")

        # ---- Load voice if editing ----
        from nicegui import app

        voice_id_to_load = app.storage.general.get("edit_voice_id", None)
        if voice_id_to_load:
            voice = lib.get_voice(voice_id_to_load)
            if voice:
                voice_id = voice_id_to_load
                set_sliders_from_voice(voice)
        else:
            reset_to_system_defaults()

        container.switch_to_gallery = None

    return container


async def generate_preview(text: str, params: dict, ref_wav_path: Optional[Path] = None) -> Path:
    """Generate a preview WAV and return its path."""
    from bookforge.config import PresetConfig
    from bookforge.process.chunker import Chunk
    from bookforge.tts.factory import get_backend

    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)
    out_path = temp_dir / f"preview_{int(datetime.now(timezone.utc).timestamp())}.wav"

    backend_type = "xtts"
    speaker_wav = ref_wav_path if ref_wav_path and ref_wav_path.exists() else None
    tts_backend = await asyncio.to_thread(
        get_backend,
        backend_type=backend_type,
        speaker_wav=speaker_wav,
        **{
            k: v
            for k, v in params.items()
            if k
            in ["temperature", "length_penalty", "repetition_penalty", "top_p", "top_k", "language"]
        },
    )

    config = PresetConfig.load(params.get("preset_name", "calm_longform"))
    chunk = Chunk(id=9999, chapter_index=0, relative_index=0, text=text, estimated_seconds=10.0)
    await asyncio.to_thread(tts_backend.synthesize_chunk, chunk, config, out_path)
    return out_path
