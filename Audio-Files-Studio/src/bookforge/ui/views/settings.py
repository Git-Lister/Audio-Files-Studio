# src/bookforge/ui/views/settings.py
"""Settings view – presets, dark mode, defaults."""

from __future__ import annotations

import asyncio

from nicegui import ui

from bookforge.config import PresetConfig
from bookforge.ui import state
from bookforge.ui.components import safe_notify


def view(on_dark_toggle=None):
    container = ui.column().classes("w-full")

    with container:
        ui.label("⚙️ Settings").classes("text-h5 q-mb-md")
        ui.markdown("Manage your voice presets and application preferences.")

        # ---- Dark mode (synchronized with header) ----
        with ui.row().classes("items-center gap-2 q-mb-md"):
            ui.label("Dark mode").classes("text-caption")
            dark_toggle = ui.switch(value=state.get_dark_mode())
            # Store reference so main.py can update it
            state._settings_dark_toggle = dark_toggle
            dark_toggle.on_value_change(
                lambda e: on_dark_toggle(e.value) if on_dark_toggle else None
            )

        # ---- Expert mode ----
        with ui.row().classes("items-center gap-2 q-mb-md"):
            ui.label("Expert mode (show advanced controls)").classes("text-caption")
            expert_toggle = ui.switch(value=state.get_expert_mode())
            expert_toggle.on_value_change(lambda e: state.set_expert_mode(e.value))

        ui.separator()

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

        with ui.row().classes("items-center gap-2 q-mb-md"):
            ui.button("Refresh List", on_click=refresh_preset_list).props("flat color=primary")

        # ---- Default backend ----
        with ui.row().classes("items-center gap-2 q-mt-md"):
            ui.label("Default TTS backend").classes("text-caption")
            backend_select = ui.select(
                options=["xtts", "piper"],
                value=state.get_state("default_backend", "xtts"),
            ).classes("w-48")
            backend_select.on_value_change(lambda e: state.set_state("default_backend", e.value))

        asyncio.create_task(refresh_preset_list())

    return container
