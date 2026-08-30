# src/bookforge/ui/views/settings.py
"""Settings view – includes preset management, backend options, and future config."""

from __future__ import annotations

import asyncio
from pathlib import Path

from nicegui import ui

from bookforge.config import PresetConfig
from bookforge.ui.components import safe_notify


def view():
    container = ui.column().classes("w-full")

    with container:
        ui.label("⚙️ Settings").classes("text-h5 q-mb-md")
        ui.markdown("Manage your voice presets and application preferences.")

        # ---- Preset Management ----
        ui.label("Voice Presets").classes("text-h6 q-mt-md")
        preset_list = ui.column().classes("w-full")

        async def refresh_preset_list():
            preset_list.clear()
            with preset_list:
                presets = PresetConfig.list_presets()
                if not presets["system"] and not presets["user"]:
                    ui.label("No presets found.").classes("text-grey")
                    return

                if presets["system"]:
                    ui.label("Built‑in Presets (read‑only)").classes("text-subtitle2 text-grey-7")
                    for name in presets["system"]:
                        with ui.row().classes("items-center gap-2 q-pa-sm"):
                            ui.label(f"📁 {name}").classes("text-caption")
                            ui.space()
                            ui.label("built‑in").classes("text-grey-6")

                if presets["user"]:
                    ui.label("Your Presets").classes("text-subtitle2 text-grey-7 q-mt-md")
                    for name in presets["user"]:
                        with ui.row().classes("items-center gap-2 q-pa-sm"):
                            ui.label(f"📄 {name}").classes("text-caption")
                            ui.space()
                            ui.button(
                                "Delete",
                                on_click=lambda n=name: delete_preset(n),
                            ).props("flat color=negative size=sm")

        async def delete_preset(name: str):
            if PresetConfig.delete_user_preset(name):
                safe_notify(f"Deleted preset '{name}'", type="positive")
                await refresh_preset_list()
            else:
                safe_notify(f"Preset '{name}' not found.", type="negative")

        # ---- Add a "refresh" button ----
        with ui.row().classes("items-center gap-2 q-mb-md"):
            ui.button("Refresh List", on_click=refresh_preset_list).props("flat color=primary")

        # ---- Future settings (placeholders) ----
        ui.label("Application Preferences").classes("text-h6 q-mt-lg")
        ui.markdown("More settings will appear here in future releases.")

        # Initial load
        asyncio.create_task(refresh_preset_list())

    return container
