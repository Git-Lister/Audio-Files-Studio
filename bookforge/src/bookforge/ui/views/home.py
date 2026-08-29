"""
Home view – entry point with cards for New Project and My Projects.
"""

from nicegui import ui


def view(on_new_project, on_projects):
    container = ui.column().classes("w-full")
    with container:
        with ui.card().classes("w-full q-pa-xl text-center"):
            ui.label("🎙️ Audio‑Files Studio").classes("text-h3 text-primary")
            ui.markdown("Create audiobooks from text files using local TTS engines.").classes(
                "q-mb-xl"
            )
            with ui.row().classes("justify-center gap-8"):
                new_card = ui.card().classes("cursor-pointer col-5")
                with new_card:
                    ui.label("📖 New Project").classes("text-h5")
                    ui.markdown("Start a fresh audiobook.")
                    ui.tooltip("Begin creating a completely new audiobook")
                new_card.on("click", on_new_project)

                projects_card = ui.card().classes("cursor-pointer col-5")
                with projects_card:
                    ui.label("📚 My Projects").classes("text-h5")
                    ui.markdown("Resume, review, or listen.")
                    ui.tooltip("Manage your existing projects")
                projects_card.on("click", on_projects)
    return container
