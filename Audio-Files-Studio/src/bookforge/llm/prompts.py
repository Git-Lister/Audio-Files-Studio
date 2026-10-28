"""Prompt templates for the LLM Executor."""

from __future__ import annotations


EXECUTOR_SYSTEM_PROMPT = """You are a text-analysis assistant. You help prepare extracted documents for text-to-speech reading.

Your task: given a numbered list of lines, classify each line as one of:
- "keep": normal prose or dialogue that should be read aloud.
- "remove": artifacts such as running headers, page numbers, journal metadata, URLs, or boilerplate that should NOT be read aloud.
- "heading": a chapter or section title that should be marked as a structural boundary.
- "uncertain": you cannot confidently classify this line.

Rules:
- Preserve the author's prose. Never suggest removing anything that is part of the narrative or argument.
- Running headers (e.g. a journal name followed by a volume number) should be removed.
- Standalone page numbers should be removed.
- URLs, DOIs, and email addresses should be removed.
- Author names and affiliations at the very top of an academic paper should be removed.
- References and bibliography entries should be classified as "keep" (the user decides whether to include them).
- When in doubt, use "uncertain".
- Keep output compact. Each decision must fit on one line of JSON.

Output: a JSON object with one key, "line_decisions", an array. Each element has:
  - "index": the line number (integer, matches the input)
  - "action": one of "keep", "remove", "heading", "uncertain"
  - "reason": a short phrase (max 5 words). Be concise.
  - "confidence": "high", "medium", or "low"

Return only the JSON object, no other text."""


def build_system_prompt(user_instructions: str | None = None, document_type: str | None = None) -> str:
    """Compose the system prompt from the base rules plus optional user
    instructions.

    User instructions are appended as a clearly-delimited section. They
    refine the base rules but do not replace them. If the user says
    something that contradicts a base rule (e.g. "keep running headers"),
    the model may still follow the base rule; we do not attempt to
    enforce precedence here.
    """
    base = EXECUTOR_SYSTEM_PROMPT

    type_rules = {
        "Academic": (
            "\n\nDOCUMENT CONTEXT: ACADEMIC PAPER.\n"
            "This is an academic paper. Remove running headers, page numbers, "
            "footnotes, and inline citation numbers. Be aggressive about stripping metadata."
        ),
        "Fiction": (
            "\n\nDOCUMENT CONTEXT: FICTION.\n"
            "This is a novel or story. Keep all prose, including chapter headings and "
            "author notes. Only remove obvious printing artifacts."
        ),
        "Script": (
            "\n\nDOCUMENT CONTEXT: REHEARSAL SCRIPT.\n"
            "This is a script. Remove stage directions in brackets [like this], "
            "time markers [00:15], and pause notations (//). Keep only the spoken dialogue."
        ),
    }

    if document_type and document_type in type_rules:
        base += type_rules[document_type]

    if not user_instructions or not user_instructions.strip():
        return base

    cleaned = user_instructions.strip()
    # Cap instructions at a reasonable length. Longer instructions dilute
    # the base prompt and rarely help.
    if len(cleaned) > 2000:
        cleaned = cleaned[:2000] + " [...]"

    return (
        base
        + "\n\nADDITIONAL USER INSTRUCTIONS:\n"
        + "The user of this tool has provided the following guidance for "
        + "this specific document. Apply it in addition to the rules above.\n\n"
        + cleaned
    )


def build_executor_user_prompt(numbered_lines: str) -> str:
    return (
        "Classify each line of the following document. The lines are "
        "numbered for reference; do not include the numbers in the output.\n\n"
        f"{numbered_lines}"
    )