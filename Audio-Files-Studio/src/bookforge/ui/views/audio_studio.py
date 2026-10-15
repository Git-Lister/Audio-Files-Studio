# src/bookforge/ui/views/audio_studio.py
"""Audio Studio – single-file editing with waveform, playback, selection, and export."""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import uuid
from pathlib import Path

from nicegui import ui

from bookforge.audio.editor import delete_range, new_working_copy, snapshot, trim
from bookforge.audio.peaks import TEMP_STUDIO_DIR, extract_peaks, get_metadata, get_duration
from bookforge.ui.components import safe_notify

AUDIO_EDITS_DIR = Path("audio_edits")


ui.add_body_html("""
<script>
    // ============ Audio Studio waveform ============
    // All JS for the waveform canvas lives here. Functions called
    // from Python must be assigned to window.

    let studioPeaks = [];
    let studioDuration = 0;
    let studioSelectionStart = 0;
    let studioSelectionEnd = 0;
    let studioIsSelecting = false;
    let studioSelectStartX = 0;

    window.setStudioPeaks = function(peaks, duration) {
        studioPeaks = peaks;
        studioDuration = duration;
        studioSelectionStart = 0;
        studioSelectionEnd = 0;
        window.drawStudioWaveform();
    };

    // Emit event to Python via NiceGUI
    function emitEvent(eventName, payload) {
        if (typeof window.emitEvent === 'function') {
            window.emitEvent(eventName, payload);
        } else {
            console.warn('Audio Studio: emitEvent not available, falling back to hidden input');
            const input = document.getElementById('studio_selection');
            if (input) {
                input.value = JSON.stringify(payload);
                input.dispatchEvent(new Event('change'));
            }
        }
    }

    window.drawStudioWaveform = function() {
        const canvas = document.getElementById('studioWaveform');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;

        const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const bg = dark ? '#1e1e1e' : '#f0f0f0';
        const wave = dark ? '#8888cc' : '#4a4a8a';
        const mid = dark ? '#444' : '#ccc';
        const playheadColor = '#e74c3c';

        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, w, h);

        const midY = h / 2;
        const halfH = h / 2 - 6;

        // Centre line
        ctx.strokeStyle = mid;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, midY);
        ctx.lineTo(w, midY);
        ctx.stroke();

        if (!studioPeaks.length) return;

        // Selection overlay
        if (studioSelectionEnd > studioSelectionStart && studioDuration > 0) {
            const sx = (studioSelectionStart / studioDuration) * w;
            const ex = (studioSelectionEnd / studioDuration) * w;
            ctx.fillStyle = 'rgba(100, 150, 255, 0.3)';
            ctx.fillRect(sx, 0, ex - sx, h);
        }

        // Waveform
        ctx.strokeStyle = wave;
        ctx.lineWidth = 1;
        const step = w / studioPeaks.length;
        for (let i = 0; i < studioPeaks.length; i++) {
            const [mn, mx] = studioPeaks[i];
            const x = i * step;
            const y1 = midY - mx * halfH;
            const y2 = midY - mn * halfH;
            ctx.beginPath();
            ctx.moveTo(x, y1);
            ctx.lineTo(x, y2);
            ctx.stroke();
        }

        // Playhead
        const audio = document.querySelector('audio');
        if (audio && studioDuration > 0) {
            const px = (audio.currentTime / studioDuration) * w;
            ctx.strokeStyle = playheadColor;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(px, 0);
            ctx.lineTo(px, h);
            ctx.stroke();
        }
    };

    window.updateStudioPlayhead = function() {
        const audio = document.querySelector('audio');
        if (audio) {
            const t = audio.currentTime;
            const total = studioDuration;
            const display = document.getElementById('studio_time_display');
            if (display) {
                display.textContent = formatTime(t) + ' / ' + formatTime(total);
            }
            window.drawStudioWaveform();
        }
        requestAnimationFrame(window.updateStudioPlayhead);
    };

    function formatTime(sec) {
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60);
        return m + ':' + (s < 10 ? '0' : '') + s;
    }

    function getMouseX(e, canvas) {
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        return (e.clientX - rect.left) * scaleX;
    }

    function sendSelection(startSec, endSec) {
        if (typeof emitEvent === 'function') {
            emitEvent('studio_selection', {start: startSec, end: endSec});
        } else {
            console.warn('Audio Studio: emitEvent not available, falling back to hidden input');
            const input = document.getElementById('studio_selection');
            if (input) {
                input.value = JSON.stringify({start: startSec, end: endSec});
                input.dispatchEvent(new Event('change'));
            }
        }
    }

    function attachStudioListeners() {
        const canvas = document.getElementById('studioWaveform');
        if (!canvas) {
            setTimeout(attachStudioListeners, 200);
            return;
        }

        canvas.addEventListener('mousedown', function(e) {
            const x = getMouseX(e, canvas);
            studioSelectStartX = x;
            studioIsSelecting = true;
            window.drawStudioWaveform();
        });

        canvas.addEventListener('mousemove', function(e) {
            if (!studioIsSelecting) return;
            const x = getMouseX(e, canvas);
            const w = canvas.width;
            const startPx = Math.min(studioSelectStartX, x);
            const endPx = Math.max(studioSelectStartX, x);
            if (studioDuration > 0) {
                studioSelectionStart = (startPx / w) * studioDuration;
                studioSelectionEnd = (endPx / w) * studioDuration;
                window.drawStudioWaveform();
            }
        });

        canvas.addEventListener('mouseup', function(e) {
            if (!studioIsSelecting) return;
            studioIsSelecting = false;
            const x = getMouseX(e, canvas);
            const w = canvas.width;
            const clickTol = 3;  // pixels — below this, treat as click, not drag
            if (Math.abs(x - studioSelectStartX) < clickTol) {
                // Single click -> seek
                if (studioDuration > 0) {
                    const t = (x / w) * studioDuration;
                    const audio = document.querySelector('audio');
                    if (audio) audio.currentTime = t;
                }
                studioSelectionStart = 0;
                studioSelectionEnd = 0;
                sendSelection(0, 0);
            } else {
                sendSelection(studioSelectionStart, studioSelectionEnd);
            }
            window.drawStudioWaveform();
        });

        canvas.addEventListener('mouseleave', function() {
            studioIsSelecting = false;
        });

        requestAnimationFrame(window.updateStudioPlayhead);
    }

    // Retry until the canvas exists
    attachStudioListeners();
</script>
""", shared=True)


def _sanitise_filename(name: str) -> str:
    """Replace non-filename-safe characters with underscores."""
    return re.sub(r"[^a-zA-Z0-9 _.-]", "_", name)


def view():
    container = ui.column().classes("w-full")

    # ---- View state ----
    state = {
        "source_path": None,       # original uploaded file
        "working_path": None,      # working copy (edited)
        "duration": 0.0,
        "peaks": [],               # list of (min, max) tuples
        "selection_start": 0.0,
        "selection_end": 0.0,
        "has_selection": False,
        "undo_stack": [],          # list of snapshot Paths
        "redo_stack": [],
        "session_dir": None,
        "playing": False,
    }

    # ---- UI elements (defined later) ----
    metadata_label: ui.label | None = None
    waveform_canvas_html: ui.html | None = None
    audio_player: ui.audio | None = None
    selection_label: ui.label | None = None
    play_btn: ui.button | None = None
    trim_btn: ui.button | None = None
    delete_btn: ui.button | None = None
    undo_btn: ui.button | None = None
    redo_btn: ui.button | None = None
    export_filename: ui.input | None = None
    export_btn: ui.button | None = None
    clear_btn: ui.button | None = None

    # ---- Helpers ----
    def update_ui_state():
        """Enable/disable buttons based on current state."""
        has_file = state["working_path"] is not None
        has_sel = state["has_selection"]

        if trim_btn:
            try:
                trim_btn.enabled = has_file and has_sel
            except RuntimeError:
                pass
        if delete_btn:
            try:
                delete_btn.enabled = has_file and has_sel
            except RuntimeError:
                pass
        if undo_btn:
            try:
                undo_btn.enabled = has_file and len(state["undo_stack"]) > 0
            except RuntimeError:
                pass
        if redo_btn:
            try:
                redo_btn.enabled = has_file and len(state["redo_stack"]) > 0
            except RuntimeError:
                pass
        if export_btn:
            try:
                export_btn.enabled = has_file
            except RuntimeError:
                pass
        if clear_btn:
            try:
                clear_btn.visible = has_file
            except RuntimeError:
                pass

        # Update selection label
        if selection_label:
            try:
                if has_sel:
                    sel_dur = state["selection_end"] - state["selection_start"]
                    selection_label.set_text(
                        f"Selection: {state['selection_start']:.1f}s – "
                        f"{state['selection_end']:.1f}s ({sel_dur:.1f}s)"
                    )
                else:
                    selection_label.set_text("No selection")
            except RuntimeError:
                pass

    def on_selection_received(e) -> None:
        """Handle a selection event emitted from the JS canvas."""
        payload = e.args if hasattr(e, "args") else {}
        try:
            start = float(payload.get("start", 0.0))
            end = float(payload.get("end", 0.0))
        except (TypeError, ValueError):
            return

        state["selection_start"] = start
        state["selection_end"] = end
        state["has_selection"] = end > start

        # Update the selection readout label if it exists
        if selection_label is not None:
            try:
                if end > start:
                    selection_label.set_text(
                        f"Selection: {start:.2f}s \u2013 {end:.2f}s ({end - start:.2f}s)"
                    )
                else:
                    selection_label.set_text("No selection")
            except RuntimeError:
                pass

        # Enable or disable the operation buttons
        has_selection = end > start
        for btn in (trim_btn, delete_btn):
            if btn is None:
                continue
            try:
                if has_selection:
                    btn.enable()
                else:
                    btn.disable()
            except RuntimeError:
                pass

    def do_play() -> None:
        """Start playback of the working file."""
        if not state["working_path"]:
            safe_notify("No file loaded", type="warning")
            return
        ui.run_javascript("""
            (function() {
                const a = document.querySelector('audio');
                if (!a) {
                    console.warn('Audio Studio: no <audio> element found');
                    return;
                }
                a.play().catch(function(err) {
                    console.error('Audio Studio: play() rejected:', err);
                });
            })();
        """)

    def do_stop() -> None:
        """Stop playback and return to the start."""
        ui.run_javascript("""
            (function() {
                const a = document.querySelector('audio');
                if (!a) return;
                a.pause();
                a.currentTime = 0;
                // Trigger a redraw of the waveform so the playhead resets
                if (typeof window.drawStudioWaveform === 'function') {
                    window.drawStudioWaveform();
                }
            })();
        """)

    def set_audio_source(path: Path):
        """Update audio player source with cache-busting."""
        if audio_player:
            try:
                # Add query param to bust cache
                audio_player.set_source(str(path) + f"?v={uuid.uuid4().hex[:8]}")
            except RuntimeError:
                pass
        # Debug log
        print(f"[AudioStudio] Set audio source to: {path}")

    def push_peaks_to_js():
        """Send peaks data to JavaScript for waveform rendering."""
        try:
            peaks_json = json.dumps(state["peaks"])
            duration = state.get("duration", 0.0)
            ui.run_javascript(f"window.setStudioPeaks && window.setStudioPeaks({peaks_json}, {duration})")
        except Exception as e:
            print(f"Failed to push peaks to JS: {e}")

    async def handle_upload(e) -> None:
        """Receive upload, extract peaks and metadata, set up working copy."""
        try:
            # Save uploaded file
            suffix = Path(e.file.name).suffix.lower()
            temp_name = f"upload_{uuid.uuid4().hex[:8]}{suffix}"
            temp_path = TEMP_STUDIO_DIR / temp_name
            TEMP_STUDIO_DIR.mkdir(parents=True, exist_ok=True)
            content = await e.file.read()
            with open(temp_path, "wb") as f:
                f.write(content)

            # Get metadata
            meta = get_metadata(temp_path)

            # Create session dir first, then working copy inside it
            from bookforge.audio.editor import new_session_dir
            session_dir = new_session_dir()
            state["session_dir"] = session_dir

            working = new_working_copy(temp_path, session_dir=session_dir)
            print(f"[AudioStudio] Working copy created: {working} exists={working.exists()}")

            # Fail loudly if the working file wasn't created
            if not working.exists():
                safe_notify(
                    f"Working file was not created: {working}",
                    type="negative",
                )
                return
            print(f"[AudioStudio] handle_upload confirmed working file exists: {working}")

            # Extract peaks
            peaks = extract_peaks(working)

            # Update state - store resolved paths
            state["source_path"] = temp_path.resolve()
            state["working_path"] = working
            state["duration"] = meta["duration"]
            state["peaks"] = peaks
            state["selection_start"] = 0.0
            state["selection_end"] = 0.0
            state["has_selection"] = False
            state["undo_stack"] = []
            state["redo_stack"] = []
            state["session_dir"] = str(session_dir)

            # Update UI
            if metadata_label:
                metadata_label.set_text(
                    f"{Path(e.file.name).name} · {meta['duration']:.2f}s · "
                    f"{meta['sample_rate']} Hz · {meta['channels']} ch · "
                    f"{meta['size_mb']:.1f} MB"
                )
            if clear_btn:
                try:
                    clear_btn.visible = True
                except RuntimeError:
                    pass

            set_audio_source(working)
            push_peaks_to_js()
            update_ui_state()

            safe_notify(f"Loaded: {Path(e.file.name).name}", type="positive")

        except Exception as ex:
            safe_notify(f"Upload failed: {ex}", type="negative")

    def do_trim() -> None:
        """Trim working file to current selection."""
        print(f"[AudioStudio.view] do_trim: working={state.get('working_path')}")
        print(f"[AudioStudio.view]   exists: {Path(state['working_path']).exists() if state.get('working_path') else 'no path'}")

        if not state["has_selection"] or not state["working_path"]:
            safe_notify("No selection to trim", type="warning")
            return

        start = max(0.0, float(state.get("selection_start", 0.0)))
        end = min(float(state.get("duration", 0.0)), float(state.get("selection_end", 0.0)))
        if end - start < 0.05:
            safe_notify("Selection is too small to operate on.", type="warning")
            return

        # Snapshot for undo
        session_dir = Path(state["session_dir"]) if state["session_dir"] else None
        if not session_dir or not session_dir.exists():
            from bookforge.audio.editor import _ensure_session_dir
            session_dir = _ensure_session_dir()
            state["session_dir"] = str(session_dir)

        print(f"[AudioStudio.view] do_trim about to snapshot {state.get('working_path')}")
        snap = snapshot(state["working_path"], session_dir)
        print(f"[AudioStudio.view] do_trim snapshot returned: {snap}")
        state["undo_stack"].append(str(snap))
        state["redo_stack"].clear()

        # Perform trim
        try:
            trim(state["working_path"], start, end)
        except Exception as ex:
            safe_notify(f"Trim failed: {ex}", type="negative")
            # Restore snapshot
            if state["undo_stack"]:
                last = Path(state["undo_stack"].pop())
                if last.exists():
                    last.replace(state["working_path"])
            return

        # Re-extract peaks
        state["peaks"] = extract_peaks(state["working_path"])
        state["duration"] = get_duration(state["working_path"])
        state["selection_start"] = 0.0
        state["selection_end"] = 0.0
        state["has_selection"] = False

        # Clear selection state and disable buttons
        try:
            if selection_label is not None:
                selection_label.set_text("No selection")
            if trim_btn is not None:
                trim_btn.disable()
            if delete_btn is not None:
                delete_btn.disable()
        except RuntimeError:
            pass

        set_audio_source(state["working_path"])
        push_peaks_to_js()
        update_ui_state()
        safe_notify("Trimmed", type="positive")
        print(f"[AudioStudio.view] do_trim complete: working={state.get('working_path')}")
        print(f"[AudioStudio.view]   exists: {Path(state['working_path']).exists() if state.get('working_path') else 'no path'}")

    def do_delete() -> None:
        """Delete the current selection."""
        print(f"[AudioStudio.view] do_delete: working={state.get('working_path')}")
        print(f"[AudioStudio.view]   exists: {Path(state['working_path']).exists() if state.get('working_path') else 'no path'}")

        if not state["has_selection"] or not state["working_path"]:
            safe_notify("No selection to delete", type="warning")
            return

        start = max(0.0, float(state.get("selection_start", 0.0)))
        end = min(float(state.get("duration", 0.0)), float(state.get("selection_end", 0.0)))
        if end - start < 0.05:
            safe_notify("Selection is too small to operate on.", type="warning")
            return

        # Snapshot for undo
        session_dir = Path(state["session_dir"]) if state["session_dir"] else None
        if not session_dir or not session_dir.exists():
            from bookforge.audio.editor import _ensure_session_dir
            session_dir = _ensure_session_dir()
            state["session_dir"] = str(session_dir)

        print(f"[AudioStudio.view] do_delete about to snapshot {state.get('working_path')}")
        snap = snapshot(state["working_path"], session_dir)
        print(f"[AudioStudio.view] do_delete snapshot returned: {snap}")
        state["undo_stack"].append(str(snap))
        state["redo_stack"].clear()

        # Perform delete
        try:
            delete_range(state["working_path"], start, end)
        except Exception as ex:
            safe_notify(f"Delete failed: {ex}", type="negative")
            if state["undo_stack"]:
                last = Path(state["undo_stack"].pop())
                if last.exists():
                    last.replace(state["working_path"])
            return

        # Re-extract peaks
        state["peaks"] = extract_peaks(state["working_path"])
        state["duration"] = get_duration(state["working_path"])
        state["selection_start"] = 0.0
        state["selection_end"] = 0.0
        state["has_selection"] = False

        # Clear selection state and disable buttons
        try:
            if selection_label is not None:
                selection_label.set_text("No selection")
            if trim_btn is not None:
                trim_btn.disable()
            if delete_btn is not None:
                delete_btn.disable()
        except RuntimeError:
            pass

        set_audio_source(state["working_path"])
        push_peaks_to_js()
        update_ui_state()
        safe_notify("Deleted", type="positive")
        print(f"[AudioStudio.view] do_delete complete: working={state.get('working_path')}")
        print(f"[AudioStudio.view]   exists: {Path(state['working_path']).exists() if state.get('working_path') else 'no path'}")

    def do_undo() -> None:
        """Restore previous snapshot."""
        if not state["undo_stack"] or not state["working_path"]:
            safe_notify("Nothing to undo", type="warning")
            return

        # Push current to redo stack
        session_dir = Path(state["session_dir"]) if state["session_dir"] else None
        if not session_dir or not session_dir.exists():
            from bookforge.audio.editor import _ensure_session_dir
            session_dir = _ensure_session_dir()
            state["session_dir"] = str(session_dir)

        snap = snapshot(state["working_path"], session_dir)
        state["redo_stack"].append(str(snap))

        # Restore from undo stack
        last_snap = Path(state["undo_stack"].pop())
        if last_snap.exists():
            last_snap.replace(state["working_path"])

        state["peaks"] = extract_peaks(state["working_path"])
        state["duration"] = get_duration(state["working_path"])
        state["selection_start"] = 0.0
        state["selection_end"] = 0.0
        state["has_selection"] = False

        set_audio_source(state["working_path"])
        push_peaks_to_js()
        update_ui_state()
        safe_notify("Undone", type="positive")

    def do_redo() -> None:
        """Reapply the last undone change."""
        if not state["redo_stack"] or not state["working_path"]:
            safe_notify("Nothing to redo", type="warning")
            return

        # Push current to undo stack
        session_dir = Path(state["session_dir"]) if state["session_dir"] else None
        if not session_dir or not session_dir.exists():
            from bookforge.audio.editor import _ensure_session_dir
            session_dir = _ensure_session_dir()
            state["session_dir"] = str(session_dir)

        snap = snapshot(state["working_path"], session_dir)
        state["undo_stack"].append(str(snap))

        # Restore from redo stack
        last_snap = Path(state["redo_stack"].pop())
        if last_snap.exists():
            last_snap.replace(state["working_path"])

        state["peaks"] = extract_peaks(state["working_path"])
        state["duration"] = get_duration(state["working_path"])
        state["selection_start"] = 0.0
        state["selection_end"] = 0.0
        state["has_selection"] = False

        set_audio_source(state["working_path"])
        push_peaks_to_js()
        update_ui_state()
        safe_notify("Redone", type="positive")

    def do_export_wav() -> None:
        """Copy the working file to audio_edits/<name>.wav."""
        if not state["working_path"] or not state["source_path"]:
            safe_notify("No file to export", type="warning")
            return

        filename = export_filename.value if export_filename else ""
        if not filename:
            base = Path(state["source_path"]).stem
            filename = f"{_sanitise_filename(base)}_edited"

        if not filename.endswith(".wav"):
            filename += ".wav"

        AUDIO_EDITS_DIR.mkdir(parents=True, exist_ok=True)
        target = AUDIO_EDITS_DIR / filename

        try:
            import shutil
            shutil.copy2(state["working_path"], target)
            safe_notify(f"Exported to audio_edits/{filename}", type="positive")
        except Exception as ex:
            safe_notify(f"Export failed: {ex}", type="negative")

    def do_clear() -> None:
        """Clear the loaded file and reset state."""
        # Clean up temp files
        for key in ("source_path", "working_path"):
            p = Path(state[key]) if state[key] else None
            if p and p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

        # Clean up session dir
        if state["session_dir"] and Path(state["session_dir"]).exists():
            try:
                import shutil
                shutil.rmtree(state["session_dir"])
            except Exception:
                pass

        # Reset state
        state["source_path"] = None
        state["working_path"] = None
        state["duration"] = 0.0
        state["peaks"] = []
        state["selection_start"] = 0.0
        state["selection_end"] = 0.0
        state["has_selection"] = False
        state["undo_stack"] = []
        state["redo_stack"] = []
        state["session_dir"] = None

        # Reset UI
        if metadata_label:
            metadata_label.set_text("No file loaded")
        if clear_btn:
            try:
                clear_btn.visible = False
            except RuntimeError:
                pass
        if audio_player:
            try:
                audio_player.set_source("")
            except RuntimeError:
                pass
        ui.run_javascript("window.setStudioPeaks && window.setStudioPeaks([], 0)")

        update_ui_state()
        safe_notify("Cleared", type="info")

    # Register event handler after all nested functions are defined
    ui.on("studio_selection", on_selection_received)

    # ---- UI ----
    with container:
        ui.label("🎚 Audio Studio").classes("text-h5 q-mb-sm")
        ui.markdown("Edit reference audio, polish output, and combine clips.").classes("q-mb-md")

        # ---- Source card ----
        with ui.card().classes("w-full q-mb-md"):
            ui.label("Source").classes("text-h6")
            ui.upload(
                label="Load an audio file",
                on_upload=handle_upload,
                auto_upload=True,
            ).classes("w-full")

            metadata_label = ui.label("No file loaded").classes("text-caption text-grey")

            clear_btn = ui.button("Clear", on_click=do_clear).props("flat color=negative")
            clear_btn.visible = False

        # ---- Waveform card ----
        with ui.card().classes("w-full q-mb-md"):
            ui.label("Waveform").classes("text-h6")

            # Canvas + audio player
            with ui.row().classes("w-full items-center"):
                ui.html("""
                <div style="position:relative; width:100%; max-width:1200px; margin:0 auto;">
                    <canvas id="studioWaveform" width="1200" height="180"
                            style="width:100%; height:180px; border-radius:8px; display:block;"></canvas>
                </div>
                """)

            # Hidden audio player for playback (positioned off-screen but kept in DOM for play())
            audio_player = ui.audio("").classes("w-full").style(
                "position: absolute; left: -9999px; width: 1px; height: 1px; opacity: 0;"
            )

            # Playback controls
            with ui.row().classes("items-center gap-2 q-mt-md"):
                play_btn = ui.button(
                    "Play", on_click=do_play
                ).props("icon=play_arrow")
                ui.button(
                    "Stop", on_click=do_stop
                ).props("icon=stop")
                ui.label("0:00 / 0:00").props('id="studio_time_display"').classes("text-caption font-mono")

            # Selection readout
            selection_label = ui.label("No selection").classes("text-caption q-mt-sm")

        # ---- Operations card ----
        with ui.card().classes("w-full q-mb-md"):
            ui.label("Operations").classes("text-h6")
            with ui.row().classes("q-my-sm"):
                trim_btn = ui.button("Trim to selection", on_click=do_trim).props("color=primary")
                trim_btn.disable()
                delete_btn = ui.button("Delete selection", on_click=do_delete).props("color=negative")
                delete_btn.disable()
            with ui.row().classes("q-my-sm"):
                undo_btn = ui.button("Undo", on_click=do_undo).props("flat color=primary")
                redo_btn = ui.button("Redo", on_click=do_redo).props("flat color=primary")

        # ---- Export card ----
        with ui.card().classes("w-full q-mb-md"):
            ui.label("Export").classes("text-h6")
            export_filename = ui.input(label="Filename", value="").classes("w-full q-mb-sm")
            export_btn = ui.button("Save as WAV", on_click=do_export_wav).props("color=positive")

        # Initial UI state
        update_ui_state()

    return container