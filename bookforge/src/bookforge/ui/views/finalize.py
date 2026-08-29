"""
Finalize view – concatenate final audio and export.
"""

from __future__ import annotations

import asyncio

from nicegui import ui

from bookforge.ui.components import get_processor, safe_notify


def view():
    container = ui.column().classes("w-full")
    with container:
        ui.label("4. Finalize Book").classes("text-h5 q-mb-md")
        finalize_status = ui.label("Synthesis complete. Click to finalize.")
        finalize_btn = ui.button("Finalize Book", icon="done_all")
        audio_player = ui.audio("").classes("hidden")

        async def on_finalize():
            proc = get_processor()
            if proc is None:
                safe_notify("No active project.", type="negative")
                return
            finalize_btn.disable()
            try:
                await asyncio.to_thread(proc.finalize_book)
                book_wav = proc.output_dir / "book.wav"
                if book_wav.exists():
                    audio_player.set_source(str(book_wav))
                    audio_player.classes(remove="hidden")
                    finalize_status.set_text("✅ Audiobook ready!")
                    safe_notify("Book finalized!", type="positive")
                    container.switch_to_projects()
            except Exception as e:  # noqa: BLE001
                safe_notify(f"Finalization error: {e}", type="negative")
            finally:
                finalize_btn.enable()

        finalize_btn.on_click(lambda: on_finalize())

    container.switch_to_projects = None
    return container
