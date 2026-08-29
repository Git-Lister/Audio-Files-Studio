"""
Settings view – global preferences.
"""

from nicegui import ui


def view():
    container = ui.column().classes("w-full")
    with container:
        ui.label("Settings").classes("text-h5")
        ui.markdown("Global preferences will appear here (e.g., default backend, theme).")
    return container
