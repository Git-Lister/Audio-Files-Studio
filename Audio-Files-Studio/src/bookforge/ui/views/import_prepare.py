# src/bookforge/ui/views/import_prepare.py
"""Import & Prepare Text – turn any document into clean, TTS-ready prose."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from nicegui import ui

from bookforge.text_extract import (
    SUPPORTED_EXTENSIONS,
    ExtractionError,
    all_rules,
    clean,
    default_enabled_keys,
    extract,
)
from bookforge.ui.components import safe_notify

BOOKS_DIR = Path("books")
TEMP_DIR = Path("temp")


def _sanitise_filename(name: str) -> str:
    """Replace non-filename-safe characters with underscores."""
    return re.sub(r"[^a-zA-Z0-9 _.-]", "_", name)


def _next_available_path(books_dir: Path, base_name: str) -> Path:
    """Return books/<base_name>.txt if free, else books/<base_name>_N.txt."""
    candidate = books_dir / f"{base_name}.txt"
    if not candidate.exists():
        return candidate
    counter = 1
    while True:
        candidate = books_dir / f"{base_name}_{counter}.txt"
        if not candidate.exists():
            return candidate
        counter += 1


def view():
    container = ui.column().classes("w-full")

    # ---- View state ----
    state = {
        "raw_extraction": "",       # text as extracted, pre-cleanup
        "source_name": None,        # original file name for display + save naming
        "dirty": False,             # True if textarea differs from last programmatic set
        "last_programmatic": "",    # last value we set programmatically
    }

    rule_checkboxes: dict[str, ui.checkbox] = {}
    text_area: ui.textarea | None = None
    status_label: ui.label | None = None
    review_card: ui.card | None = None
    action_row: ui.row | None = None

    # ---- Helpers ----
    def enabled_rule_keys() -> set[str]:
        return {key for key, cb in rule_checkboxes.items() if cb.value}

    def update_status(message: str, kind: str = "info") -> None:
        if status_label is None:
            return
        try:
            color = {"info": "text-grey", "positive": "text-positive",
                     "warning": "text-warning", "negative": "text-negative"}.get(kind, "text-grey")
            status_label.set_text(message)
            status_label.classes(remove="text-grey text-positive text-warning text-negative",
                                 add=color)
        except RuntimeError:
            pass

    def set_textarea_programmatically(text: str) -> None:
        """Replace textarea content and reset the dirty baseline."""
        if text_area is None:
            return
        state["last_programmatic"] = text
        state["dirty"] = False
        try:
            text_area.value = text
        except RuntimeError:
            pass

    def on_textarea_change(e) -> None:
        if e.value != state["last_programmatic"]:
            state["dirty"] = True

    def run_cleanup() -> str:
        return clean(state["raw_extraction"], enabled_rule_keys())

    def do_reclean() -> None:
        if not state["raw_extraction"]:
            safe_notify("No extraction to clean. Upload a file first.", type="warning")
            return
        cleaned = run_cleanup()
        set_textarea_programmatically(cleaned)
        update_status(
            f"Cleaned {len(state['raw_extraction']):,} chars → {len(cleaned):,} chars.",
            "positive",
        )

    def do_reset() -> None:
        if not state["raw_extraction"]:
            return
        set_textarea_programmatically(state["raw_extraction"])
        update_status(
            f"Reset to raw extraction ({len(state['raw_extraction']):,} chars).",
            "info",
        )

    def confirm_if_dirty(action_label: str, on_confirm) -> None:
        if not state["dirty"]:
            on_confirm()
            return
        with ui.dialog() as dialog, ui.card().classes("max-w-md"):
            ui.label("Unsaved edits").classes("text-h6")
            ui.label(
                "You have made manual edits to the review pane. "
                f"Continuing will discard them and {action_label}."
            ).classes("text-caption")
            with ui.row().classes("justify-end w-full q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Continue",
                    on_click=lambda: (dialog.close(), on_confirm()),
                ).props("color=negative")
        dialog.open()

    async def handle_upload(e) -> None:
        # Save uploaded file to temp
        try:
            suffix = Path(e.file.name).suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                safe_notify(
                    f"Unsupported file type: {suffix}. "
                    f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}",
                    type="negative",
                )
                return

            temp_name = f"import_{uuid.uuid4().hex[:8]}_{e.file.name}"
            temp_path = TEMP_DIR / temp_name
            TEMP_DIR.mkdir(exist_ok=True)
            content = await e.file.read()
            with open(temp_path, "wb") as f:
                f.write(content)
        except Exception as ex:
            safe_notify(f"Upload failed: {ex}", type="negative")
            return

        # Run extraction
        try:
            raw = extract(temp_path)
        except ExtractionError as ex:
            safe_notify(f"Extraction failed: {ex}", type="negative")
            return

        if not raw.strip():
            safe_notify(
                "No text could be extracted from this file. "
                "It may be a scanned PDF or an image-only document.",
                type="warning",
            )
            return

        state["raw_extraction"] = raw
        state["source_name"] = e.file.name
        update_status(f"Extracted {len(raw):,} chars from {e.file.name}.", "positive")

        # Auto-run cleanup once
        do_reclean()

        # Reveal review area
        if review_card is not None:
            try:
                review_card.visible = True
            except RuntimeError:
                pass
        if action_row is not None:
            try:
                action_row.visible = True
            except RuntimeError:
                pass

    def do_save() -> None:
        if text_area is None:
            return
        try:
            text = text_area.value or ""
        except RuntimeError:
            return
        if not text.strip():
            safe_notify("Nothing to save — review pane is empty.", type="warning")
            return
        if state["source_name"] is None:
            safe_notify("No source file recorded. Upload first.", type="warning")
            return

        base_name = _sanitise_filename(Path(state["source_name"]).stem)
        BOOKS_DIR.mkdir(exist_ok=True)
        target = _next_available_path(BOOKS_DIR, base_name)
        try:
            target.write_text(text, encoding="utf-8")
        except OSError as ex:
            safe_notify(f"Save failed: {ex}", type="negative")
            return
        safe_notify(f"Saved to books/{target.name}", type="positive")
        update_status(f"Saved to books/{target.name} ({len(text):,} chars).", "positive")

    def do_discard() -> None:
        state["raw_extraction"] = ""
        state["source_name"] = None
        state["dirty"] = False
        state["last_programmatic"] = ""
        if text_area is not None:
            try:
                text_area.value = ""
            except RuntimeError:
                pass
        if review_card is not None:
            try:
                review_card.visible = False
            except RuntimeError:
                pass
        if action_row is not None:
            try:
                action_row.visible = False
            except RuntimeError:
                pass
        update_status("Discarded. Ready for a new file.", "info")

    # ---- UI ----
    with container:
        ui.label("🧹 Import & Prepare Text").classes("text-h5 q-mb-md")
        ui.markdown(
            "Turn any document into clean, TTS-ready prose. "
            "The cleaned text is saved to **books/** and appears in the New Project wizard."
        )

        # --- Upload card ---
        with ui.card().classes("w-full q-mb-md"):
            ui.label("1. Upload a document").classes("text-h6")
            ui.markdown(
                "Supported formats: " + ", ".join(f"`{e}`" for e in SUPPORTED_EXTENSIONS)
            )
            ui.upload(
                label="Drag a file here, or select",
                on_upload=handle_upload,
                auto_upload=True,
            ).classes("w-full")

        # --- Cleanup options card ---
        with ui.card().classes("w-full q-mb-md"):
            ui.label("2. Cleanup options").classes("text-h6")
            ui.markdown(
                "_Defaults are a good starting point. Adjust and click Re-Clean to apply._"
            )

            enabled_defaults = default_enabled_keys()
            rules = all_rules()
            tier1 = [r for r in rules if r.tier == 1]
            tier2 = [r for r in rules if r.tier == 2]

            with ui.expansion("Tier 1 — Cosmetic fixes", value=True).classes("w-full"):
                for rule in tier1:
                    cb = ui.checkbox(rule.label, value=rule.key in enabled_defaults)
                    with cb:
                        ui.tooltip(rule.description)
                    rule_checkboxes[rule.key] = cb

            with ui.expansion("Tier 2 — Structural fixes", value=True).classes("w-full"):
                for rule in tier2:
                    cb = ui.checkbox(rule.label, value=rule.key in enabled_defaults)
                    with cb:
                        ui.tooltip(rule.description)
                    rule_checkboxes[rule.key] = cb

        # --- Action row (hidden until upload) ---
        with ui.row().classes("q-mb-md gap-2") as action_row:
            action_row.visible = False
            ui.button("Re-Clean", on_click=lambda: confirm_if_dirty("re-clean", do_reclean)) \
                .props("color=primary")
            ui.button("Reset to extraction", on_click=lambda: confirm_if_dirty("reset", do_reset)) \
                .props("flat")
            llm_btn = ui.button("Clean up with LLM (coming soon)", on_click=lambda: None) \
                .props("flat disabled")
            with llm_btn:
                ui.tooltip(
                    "Future feature: an LLM pass to fix archaic spellings, "
                    "expand unfamiliar abbreviations, and tune punctuation for prosody."
                )

        # --- Review card (hidden until upload) ---
        with ui.card().classes("w-full q-mb-md") as review_card:
            review_card.visible = False
            ui.label("3. Review & edit").classes("text-h6")
            ui.markdown(
                "_Edit freely. Your manual changes are what gets saved._"
            )
            text_area = ui.textarea().props("rows=30 outlined").classes("w-full font-mono")
            text_area.on_value_change(on_textarea_change)

        # --- Status label ---
        status_label = ui.label("Ready. Upload a document to begin.").classes("text-caption text-grey")

        # --- Save row (always present; hidden state managed via action_row) ---
        with ui.row().classes("q-mt-md gap-2"):
            ui.button("Save to books/", on_click=do_save).props("color=positive")
            ui.button("Discard", on_click=do_discard).props("flat")

    return container