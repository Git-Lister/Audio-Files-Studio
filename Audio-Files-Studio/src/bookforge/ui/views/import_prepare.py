# src/bookforge/ui/views/import_prepare.py
"""Import & Prepare Text – turn any document into clean, TTS-ready prose."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from pathlib import Path

from nicegui import ui

from bookforge.llm import Executor as LLMExecutor
from bookforge.llm import is_available as llm_is_available
from bookforge.llm import save_run, update_run_decisions
from bookforge.text_extract import (
    SUPPORTED_EXTENSIONS,
    ExtractionError,
    all_rules,
    apply_llm_verdicts,
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
        "raw_extraction": "",  # text as extracted, pre-cleanup
        "source_name": None,  # original file name for display + save naming
        "dirty": False,  # True if textarea differs from last programmatic set
        "last_programmatic": "",  # last value we set programmatically
        # NEW: track the last applied LLM run for undo purposes
        "pre_llm_text": None,
        # NEW: track the current LLM run for later update
        "current_run_id": None,
    }

    rule_checkboxes: dict[str, ui.checkbox] = {}
    text_area: ui.textarea | None = None
    status_label: ui.label | None = None
    review_card: ui.card | None = None
    action_row: ui.row | None = None
    smart_btn: ui.button | None = None

    # ---- Helpers ----
    def enabled_rule_keys() -> set[str]:
        return {key for key, cb in rule_checkboxes.items() if cb.value}

    def update_status(message: str, kind: str = "info") -> None:
        if status_label is None:
            return
        try:
            color = {
                "info": "text-grey",
                "positive": "text-positive",
                "warning": "text-warning",
                "negative": "text-negative",
            }.get(kind, "text-grey")
            status_label.set_text(message)
            status_label.classes(
                remove="text-grey text-positive text-warning text-negative", add=color
            )
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

    async def smart_cleanup() -> None:
        """Run LLM classification on the current review-pane text and show
        a modal for the user to accept or reject proposed changes."""
        if text_area is None:
            return
        try:
            current_text = text_area.value or ""
        except RuntimeError:
            return
        if not current_text.strip():
            safe_notify("Nothing to analyse — the review pane is empty.", type="warning")
            return

        if not llm_is_available():
            safe_notify(
                "Smart Cleanup is not available: the LLM library failed to load. "
                "See the README for setup notes.",
                type="negative",
            )
            return

        # Capture pre-state for undo
        state["pre_llm_text"] = current_text

        # Show progress
        safe_notify("Analysing text with LLM. First run may take a few minutes.", type="info")
        if smart_btn is not None:
            try:
                smart_btn.disable()
            except RuntimeError:
                pass

        _start = time.monotonic()
        try:
            executor = LLMExecutor()
            result = await asyncio.to_thread(executor.classify_lines, current_text)
        except Exception as ex:
            safe_notify(f"LLM classification failed: {ex}", type="negative")
            if smart_btn is not None:
                try:
                    smart_btn.enable()
                except RuntimeError:
                    pass
            return
        _elapsed = time.monotonic() - _start

        # Persist the run
        try:
            verdicts_as_dicts = [
                {
                    "index": d.index,
                    "action": d.action,
                    "reason": d.reason,
                    "confidence": d.confidence,
                }
                for d in result.line_decisions
            ]
            run_id = save_run(
                input_text=current_text,
                verdicts=verdicts_as_dicts,
                model_name=result.model_name,
                source_name=state.get("source_name"),
                elapsed_seconds=_elapsed,
            )
            state["current_run_id"] = run_id
        except Exception as ex:
            # Persistence failing should not block the flow.
            safe_notify(f"Note: run could not be saved ({ex}).", type="warning")

        # Build modal from result
        show_llm_review_modal(current_text, result)

    def show_llm_review_modal(original_text: str, result) -> None:
        """Open a modal showing proposed changes, with per-item accept checkboxes."""
        lines = original_text.split("\n")

        removals = [d for d in result.line_decisions if d.action == "remove"]
        headings = [d for d in result.line_decisions if d.action == "heading"]
        uncertain = [d for d in result.line_decisions if d.action == "uncertain"]

        # Guard: nothing to propose
        if not removals and not headings and not uncertain:
            safe_notify("LLM found nothing to change.", type="info")
            if smart_btn is not None:
                try:
                    smart_btn.enable()
                except RuntimeError:
                    pass
            return

        accept_checks: dict[int, ui.checkbox] = {}

        with ui.dialog() as dialog, ui.card().classes("w-full max-w-3xl"):
            ui.label("Smart Cleanup — review proposed changes").classes("text-h6")
            ui.markdown(
                f"The LLM proposed **{len(removals)} removal(s)** and "
                f"**{len(headings)} heading(s)**, and flagged "
                f"**{len(uncertain)} line(s)** as uncertain."
            )

            with ui.scroll_area().classes("w-full h-96 q-my-md"):
                if removals:
                    ui.label("Proposed removals").classes("text-subtitle1 q-mt-md")
                    for d in removals:
                        if d.index < 0 or d.index >= len(lines):
                            continue
                        line_content = lines[d.index]
                        preview = line_content[:120]
                        if len(line_content) > 120:
                            preview += "…"
                        with ui.row().classes("items-start gap-2 q-py-xs"):
                            cb = ui.checkbox(value=True)
                            accept_checks[d.index] = cb
                            with ui.column().classes("gap-0"):
                                ui.label(f"Line {d.index}").classes("text-caption text-grey")
                                ui.label(preview).classes("text-caption font-mono")
                                if d.reason:
                                    ui.label(f"Reason: {d.reason} ({d.confidence})").classes(
                                        "text-caption text-grey-6"
                                    )

                if headings:
                    ui.label("Proposed headings").classes("text-subtitle1 q-mt-md")
                    for d in headings:
                        if d.index < 0 or d.index >= len(lines):
                            continue
                        line_content = lines[d.index]
                        preview = line_content[:120]
                        with ui.row().classes("items-start gap-2 q-py-xs"):
                            cb = ui.checkbox(value=True)
                            accept_checks[d.index] = cb
                            with ui.column().classes("gap-0"):
                                ui.label(f"Line {d.index} — will prefix with '# '").classes(
                                    "text-caption text-grey"
                                )
                                ui.label(preview).classes("text-caption font-mono")
                                if d.reason:
                                    ui.label(f"Reason: {d.reason} ({d.confidence})").classes(
                                        "text-caption text-grey-6"
                                    )

                if uncertain:
                    ui.label("Flagged as uncertain (no action proposed)").classes(
                        "text-subtitle1 q-mt-md"
                    )
                    for d in uncertain:
                        if d.index < 0 or d.index >= len(lines):
                            continue
                        line_content = lines[d.index]
                        preview = line_content[:120]
                        with ui.column().classes("gap-0 q-py-xs"):
                            ui.label(f"Line {d.index}").classes("text-caption text-grey")
                            ui.label(preview).classes("text-caption font-mono")
                            if d.reason:
                                ui.label(f"Note: {d.reason} ({d.confidence})").classes(
                                    "text-caption text-grey-6"
                                )

            def apply_accepted() -> None:
                accepted: dict[int, str] = {}
                rejected: dict[int, str] = {}
                for d in removals + headings:
                    cb = accept_checks.get(d.index)
                    if cb is not None:
                        if cb.value:
                            accepted[d.index] = d.action
                        else:
                            rejected[d.index] = d.action
                # Persist decisions
                run_id = state.get("current_run_id")
                if run_id is not None:
                    try:
                        update_run_decisions(run_id, accepted, rejected)
                    except Exception as ex:
                        safe_notify(f"Note: decisions could not be saved ({ex}).", type="warning")
                new_text = apply_llm_verdicts(original_text, accepted)
                set_textarea_programmatically(new_text)
                update_status(
                    f"Smart Cleanup applied: {len(accepted)} change(s).",
                    "positive",
                )
                dialog.close()
                if smart_btn is not None:
                    try:
                        smart_btn.enable()
                    except RuntimeError:
                        pass

            def cancel() -> None:
                run_id = state.get("current_run_id")
                if run_id is not None:
                    try:
                        update_run_decisions(run_id, {}, {})
                    except Exception:
                        pass
                state["pre_llm_text"] = None
                state["current_run_id"] = None
                dialog.close()
                if smart_btn is not None:
                    try:
                        smart_btn.enable()
                    except RuntimeError:
                        pass

            with ui.row().classes("justify-end w-full q-mt-md gap-2"):
                ui.button("Cancel", on_click=cancel).props("flat")
                ui.button("Apply accepted", on_click=apply_accepted).props("color=primary")

        dialog.open()

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
        state["pre_llm_text"] = None
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

    def undo_llm() -> None:
        pre = state.get("pre_llm_text")
        if pre is None:
            return
        set_textarea_programmatically(pre)
        state["pre_llm_text"] = None
        update_status("Reverted Smart Cleanup.", "info")

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
            ui.markdown("Supported formats: " + ", ".join(f"`{e}`" for e in SUPPORTED_EXTENSIONS))
            ui.upload(
                label="Drag a file here, or select",
                on_upload=handle_upload,
                auto_upload=True,
            ).classes("w-full")

        # --- Cleanup options card ---
        with ui.card().classes("w-full q-mb-md"):
            ui.label("2. Cleanup options").classes("text-h6")
            ui.markdown("_Defaults are a good starting point. Adjust and click Re-Clean to apply._")

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
            ui.button("Re-Clean", on_click=lambda: confirm_if_dirty("re-clean", do_reclean)).props(
                "color=primary"
            )
            ui.button(
                "Reset to extraction", on_click=lambda: confirm_if_dirty("reset", do_reset)
            ).props("flat")
            smart_btn = ui.button("Smart Cleanup", on_click=smart_cleanup).props("color=secondary")
            with smart_btn:
                ui.tooltip(
                    "Run a local LLM pass to identify remaining artifacts "
                    "(running headers, metadata, boilerplate). Proposed changes "
                    "are shown for review before being applied. First run "
                    "downloads the model (~2 GB)."
                )

        # --- Review card (hidden until upload) ---
        with ui.card().classes("w-full q-mb-md") as review_card:
            review_card.visible = False
            ui.label("3. Review & edit").classes("text-h6")
            ui.markdown("_Edit freely. Your manual changes are what gets saved._")
            text_area = ui.textarea().props("rows=30 outlined").classes("w-full font-mono")
            text_area.on_value_change(on_textarea_change)

        # --- Status label ---
        status_label = ui.label("Ready. Upload a document to begin.").classes(
            "text-caption text-grey"
        )

        # --- Save row (always present; hidden state managed via action_row) ---
        with ui.row().classes("q-mt-md gap-2"):
            ui.button("Save to books/", on_click=do_save).props("color=positive")
            undo_btn = ui.button("Undo Smart Cleanup", on_click=undo_llm)
            undo_btn.props("flat")
            undo_btn.visible = state.get("pre_llm_text") is not None
            ui.button("Discard", on_click=do_discard).props("flat")

    return container
