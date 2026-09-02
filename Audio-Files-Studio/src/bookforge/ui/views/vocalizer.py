# src/bookforge/ui/views/vocalizer.py
"""Vocalizer – voice editor with sliders, preview, waveform, and radar chart."""

from __future__ import annotations

import asyncio
import json
import struct
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from nicegui import app, ui

from bookforge.ui import voice_library as lib
from bookforge.ui.components import safe_notify

# ---- Debug flag ----
RADAR_DEBUG = False

# ---- Default preview texts ----
DEFAULT_PREVIEW = "This is a sample of my voice. It is clear, natural, and ready for narration."
POETIC_PREVIEW = "In th’ olde dayes of the King Arthour, Of which that Britons speken greet honour, All was this land fulfild of fayerye."
SCIENTIFIC_PREVIEW = "The quantum entanglement of the phonon field underlies the emergent properties of the vocal tract's resonance, which we model as a coupled oscillator system."

# ---- Radar axes ----
RADAR_AXES = [
    ("Expressiveness", "temperature", 0.1, 1.0),
    ("Speed", "length_penalty", 0.5, 2.0),
    ("Stability", "repetition_penalty", 1.0, 10.0),
    ("Warmth", "pitch", -5.0, 5.0),
    ("Pacing", "rate", 0.5, 2.0),
]


def param_to_radar(param_name: str, value: float) -> float:
    for label, name, min_val, max_val in RADAR_AXES:
        if name == param_name:
            return (value - min_val) / (max_val - min_val)
    return 0.5


def radar_to_param(axis_index: int, value_0_1: float) -> float:
    _, _, min_val, max_val = RADAR_AXES[axis_index]
    return min_val + value_0_1 * (max_val - min_val)


def get_radar_values(temp, length_penalty, repetition_penalty, pitch, rate) -> list:
    return [
        param_to_radar("temperature", temp),
        param_to_radar("length_penalty", length_penalty),
        param_to_radar("repetition_penalty", repetition_penalty),
        param_to_radar("pitch", pitch),
        param_to_radar("rate", rate),
    ]


def view(switch_to_gallery_callback=None):
    container = ui.column().classes("w-full")
    container.switch_to_gallery = switch_to_gallery_callback  # type: ignore

    # ---- Inject radar JavaScript once ----
    if not app.storage.general.get("radar_script_added", False):
        ui.add_body_html("""
        <script>
        // ---- Radar chart JavaScript (global) ----
        (function() {
            const NUM_AXES = 5;
            const AXIS_LABELS = ["Expressiveness", "Speed", "Stability", "Warmth", "Pacing"];
            const COLOUR_GRID = (window.matchMedia('(prefers-color-scheme: dark)').matches) ? '#666' : '#ccc';
            const COLOUR_TEXT = (window.matchMedia('(prefers-color-scheme: dark)').matches) ? '#eee' : '#333';
            const COLOUR_POLYGON = 'rgba(201, 169, 89, 0.3)';
            const COLOUR_STROKE = '#c9a959';
            const COLOUR_VERTEX = '#c9a959';
            const RADIUS = 160;
            const CENTER_X = 300;
            const CENTER_Y = 200;
            const VERTEX_RADIUS = 6;

            let currentValues = [0.5, 0.5, 0.5, 0.5, 0.5];
            let isDragging = false;
            let dragAxisIndex = -1;
            let canvas, ctx;

            function init() {
                canvas = document.getElementById('radarChart');
                if (!canvas) return;
                ctx = canvas.getContext('2d');
                drawRadarChart(currentValues);
                canvas.addEventListener('mousedown', handleMouseDown);
                canvas.addEventListener('mousemove', handleMouseMove);
                canvas.addEventListener('mouseup', handleMouseUp);
                canvas.addEventListener('mouseleave', handleMouseUp);
            }

            window.drawRadarChart = function(values) {
                if (!ctx || !canvas) return;
                currentValues = values.map(v => Math.max(0, Math.min(1, v)));
                draw();
            };

            function draw() {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                // concentric rings
                for (let i = 1; i <= 5; i++) {
                    const r = (i / 5) * RADIUS;
                    ctx.beginPath();
                    ctx.arc(CENTER_X, CENTER_Y, r, 0, 2 * Math.PI);
                    ctx.strokeStyle = COLOUR_GRID;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
                // axes
                for (let i = 0; i < NUM_AXES; i++) {
                    const angle = (i / NUM_AXES) * 2 * Math.PI - Math.PI / 2;
                    const x = CENTER_X + RADIUS * Math.cos(angle);
                    const y = CENTER_Y + RADIUS * Math.sin(angle);
                    ctx.beginPath();
                    ctx.moveTo(CENTER_X, CENTER_Y);
                    ctx.lineTo(x, y);
                    ctx.strokeStyle = COLOUR_GRID;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                    const labelX = CENTER_X + (RADIUS + 20) * Math.cos(angle);
                    const labelY = CENTER_Y + (RADIUS + 20) * Math.sin(angle);
                    ctx.fillStyle = COLOUR_TEXT;
                    ctx.font = '12px sans-serif';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(AXIS_LABELS[i], labelX, labelY);
                }
                // polygon
                const points = [];
                for (let i = 0; i < NUM_AXES; i++) {
                    const angle = (i / NUM_AXES) * 2 * Math.PI - Math.PI / 2;
                    const r = currentValues[i] * RADIUS;
                    points.push({
                        x: CENTER_X + r * Math.cos(angle),
                        y: CENTER_Y + r * Math.sin(angle)
                    });
                }
                ctx.beginPath();
                ctx.moveTo(points[0].x, points[0].y);
                for (let i = 1; i < points.length; i++) {
                    ctx.lineTo(points[i].x, points[i].y);
                }
                ctx.closePath();
                ctx.fillStyle = COLOUR_POLYGON;
                ctx.fill();
                ctx.strokeStyle = COLOUR_STROKE;
                ctx.lineWidth = 2;
                ctx.stroke();
                // vertices
                for (let i = 0; i < points.length; i++) {
                    ctx.beginPath();
                    ctx.arc(points[i].x, points[i].y, VERTEX_RADIUS, 0, 2 * Math.PI);
                    ctx.fillStyle = COLOUR_VERTEX;
                    ctx.fill();
                    ctx.strokeStyle = '#fff';
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }
            }

            function getMousePos(e) {
                const rect = canvas.getBoundingClientRect();
                const scaleX = canvas.width / rect.width;
                const scaleY = canvas.height / rect.height;
                return {
                    x: (e.clientX - rect.left) * scaleX,
                    y: (e.clientY - rect.top) * scaleY,
                };
            }

            function getClosestVertex(mx, my) {
                let minDist = 20;
                let idx = -1;
                for (let i = 0; i < NUM_AXES; i++) {
                    const angle = (i / NUM_AXES) * 2 * Math.PI - Math.PI / 2;
                    const r = currentValues[i] * RADIUS;
                    const vx = CENTER_X + r * Math.cos(angle);
                    const vy = CENTER_Y + r * Math.sin(angle);
                    const dist = Math.hypot(mx - vx, my - vy);
                    if (dist < minDist) {
                        minDist = dist;
                        idx = i;
                    }
                }
                return idx;
            }

            function handleMouseDown(e) {
                const pos = getMousePos(e);
                const idx = getClosestVertex(pos.x, pos.y);
                if (idx !== -1) {
                    isDragging = true;
                    dragAxisIndex = idx;
                    e.preventDefault();
                }
            }

            function handleMouseMove(e) {
                if (!isDragging || dragAxisIndex === -1) return;
                const pos = getMousePos(e);
                const dx = pos.x - CENTER_X;
                const dy = pos.y - CENTER_Y;
                const angle = Math.atan2(dy, dx);
                const expectedAngle = (dragAxisIndex / NUM_AXES) * 2 * Math.PI - Math.PI / 2;
                const projection = Math.cos(angle - expectedAngle);
                const distance = Math.hypot(dx, dy);
                let val = (distance * projection) / RADIUS;
                val = Math.max(0, Math.min(1, val));
                currentValues[dragAxisIndex] = val;
                draw();
                sendDragData(dragAxisIndex, val);
            }

            function handleMouseUp(e) {
                if (isDragging) {
                    isDragging = false;
                    dragAxisIndex = -1;
                }
            }

            function sendDragData(axisIndex, value) {
                const input = document.getElementById('radar_drag_input');
                if (input) {
                    input.value = JSON.stringify({axis: axisIndex, value: value});
                    input.dispatchEvent(new Event('change'));
                } else {
                    console.warn('Radar: hidden input not found');
                }
            }

            document.addEventListener('DOMContentLoaded', init);
            if (document.readyState === 'complete' || document.readyState === 'interactive') {
                init();
            }
        })();
        </script>
        """)
        app.storage.general["radar_script_added"] = True

    # ---- State ----
    voice_id = None
    uploaded_ref_path: Optional[Path] = None

    # ---- UI controls (initialised later) ----
    name_input = None
    desc_input = None
    tags_input = None
    preview_textarea = None

    temp_slider = None
    length_slider = None
    repeat_slider = None
    pitch_slider = None
    rate_slider = None

    top_p_slider = None
    top_k_slider = None

    normalize_check = None
    ref_status = None
    generate_btn = None
    preview_spinner = None
    audio_player = None

    # ---- Helper functions ----
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
        update_radar_chart()

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

    def update_radar_chart():
        values = get_radar_values(
            temp_slider.value,
            length_slider.value,
            repeat_slider.value,
            pitch_slider.value,
            rate_slider.value,
        )
        ui.run_javascript(f"drawRadarChart({values})")

    def check_radar_drag():
        data = app.storage.general.get("radar_drag_data", "")
        if data:
            app.storage.general["radar_drag_data"] = ""
            try:
                parsed = json.loads(data)
                axis_idx = parsed["axis"]
                new_val_0_1 = parsed["value"]
                new_val_0_1 = max(0.0, min(1.0, new_val_0_1))
                new_param = radar_to_param(axis_idx, new_val_0_1)
                param_name = RADAR_AXES[axis_idx][1]
                if param_name == "temperature":
                    temp_slider.value = new_param
                elif param_name == "length_penalty":
                    length_slider.value = new_param
                elif param_name == "repetition_penalty":
                    repeat_slider.value = new_param
                elif param_name == "pitch":
                    pitch_slider.value = new_param
                elif param_name == "rate":
                    rate_slider.value = new_param
                if RADAR_DEBUG:
                    safe_notify(
                        f"Radar drag: {RADAR_AXES[axis_idx][0]} → {new_param:.3f}", type="info"
                    )
            except Exception as e:
                safe_notify(f"Radar drag error: {e}", type="warning")

    async def handle_upload(e):
        nonlocal uploaded_ref_path
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        unique_name = f"ref_{uuid.uuid4().hex[:8]}.wav"
        ref_path = temp_dir / unique_name
        content = await e.file.read()
        with open(ref_path, "wb") as f:
            f.write(content)
        uploaded_ref_path = ref_path
        ref_status.set_text(f"Reference: {e.file.name} (uploaded)")
        safe_notify("Reference WAV uploaded.", type="positive")
        if RADAR_DEBUG:
            print(f"📁 Uploaded reference to: {ref_path}")

    async def generate_preview_action():
        preview_spinner.visible = True
        generate_btn.disable()
        try:
            text = preview_textarea.value or DEFAULT_PREVIEW
            params = get_current_params()
            ref_path_to_use = uploaded_ref_path
            if ref_path_to_use is None and voice_id:
                voice = lib.get_voice(voice_id)
                if voice and voice.get("reference_wav_path"):
                    ref_path_to_use = Path(voice["reference_wav_path"])
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
        if container.switch_to_gallery:  # type: ignore
            container.switch_to_gallery()  # type: ignore
        else:
            safe_notify("Return to Gallery not configured.", type="warning")

    # ---- Build UI ----
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
                ui.label("Voice Character (Radar)").classes("text-h6 text-bold")
                ui.markdown("_These sliders control the overall personality of the voice._")

                temp_slider = ui.slider(min=0.1, max=1.0, step=0.01, value=0.667).classes("w-full")
                ui.label().bind_text_from(
                    temp_slider, "value", backward=lambda v: f"Expressiveness (temp): {v:.2f}"
                )
                temp_slider.on_value_change(update_radar_chart)

                length_slider = ui.slider(min=0.5, max=2.0, step=0.05, value=1.0).classes("w-full")
                ui.label().bind_text_from(
                    length_slider, "value", backward=lambda v: f"Speed (len pen): {v:.2f}"
                )
                length_slider.on_value_change(update_radar_chart)

                repeat_slider = ui.slider(min=1.0, max=10.0, step=0.5, value=5.0).classes("w-full")
                ui.label().bind_text_from(
                    repeat_slider, "value", backward=lambda v: f"Stability (rep pen): {v:.1f}"
                )
                repeat_slider.on_value_change(update_radar_chart)

                pitch_slider = ui.slider(min=-5, max=5, step=0.5, value=0).classes("w-full")
                ui.label().bind_text_from(
                    pitch_slider, "value", backward=lambda v: f"Warmth (pitch): {v:.1f}"
                )
                pitch_slider.on_value_change(update_radar_chart)

                rate_slider = ui.slider(min=0.5, max=2.0, step=0.05, value=1.0).classes("w-full")
                ui.label().bind_text_from(
                    rate_slider, "value", backward=lambda v: f"Pacing (rate): {v:.2f}"
                )
                rate_slider.on_value_change(update_radar_chart)

                ui.separator().classes("q-mt-md")

                ui.label("Advanced Sampling").classes("text-h6 text-bold q-mt-md")
                ui.markdown("_Fine‑tune the sampling strategy. These are not shown on the radar._")

                top_p_slider = ui.slider(min=0.0, max=1.0, step=0.01, value=0.8).classes("w-full")
                ui.label().bind_text_from(
                    top_p_slider, "value", backward=lambda v: f"Top‑P (nucleus): {v:.2f}"
                )

                top_k_slider = ui.slider(min=0, max=100, step=1, value=50).classes("w-full")
                ui.label().bind_text_from(
                    top_k_slider, "value", backward=lambda v: f"Top‑K (diversity): {int(v)}"
                )

                normalize_check = ui.checkbox("Normalize volume", value=False)

                ui.label("Reference WAV").classes("text-h6 q-mt-md")
                ui.upload(
                    label="Upload reference WAV", auto_upload=True, on_upload=handle_upload
                ).classes("w-full")
                ref_status = ui.label("No reference uploaded").classes("text-caption text-grey")

                with ui.row().classes("q-mt-md"):
                    ui.button("Reset to Loaded", on_click=reset_to_loaded).props("flat")
                    ui.button("System Defaults", on_click=reset_to_system_defaults).props("flat")

            with ui.column().classes("w-2/3"):
                with ui.card().classes("w-full q-mb-md"):
                    ui.label("Voice Fingerprint").classes("text-h6")
                    # Hidden input with explicit type and id
                    radar_drag_input = (
                        ui.input(value="")
                        .props('type="hidden" id="radar_drag_input"')
                        .bind_value_to(app.storage.general, "radar_drag_data")
                    )
                    # Canvas only – no script
                    ui.html("""
                    <div style="position:relative; width:100%; max-width:600px; margin:0 auto;">
                        <canvas id="radarChart" width="600" height="400"></canvas>
                    </div>
                    """)

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
        voice_id_to_load = app.storage.general.get("edit_voice_id", None)
        if voice_id_to_load:
            voice = lib.get_voice(voice_id_to_load)
            if voice:
                voice_id = voice_id_to_load
                set_sliders_from_voice(voice)
        else:
            reset_to_system_defaults()

        ui.timer(0.1, check_radar_drag)

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
