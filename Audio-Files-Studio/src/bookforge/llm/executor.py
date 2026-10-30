"""Executor: runs a classification pass against a local LLM."""

from __future__ import annotations

import logging

from .engine import LLMEngine, get_engine
from .prompts import build_executor_user_prompt, build_system_prompt
from .schemas import ExecutorResult, LineDecision

logger = logging.getLogger("bookforge.llm.executor")


def _classify_batch(
    engine,
    lines: list[str],
    absolute_start: int,
    system_prompt: str,
    build_user_prompt,
) -> list[LineDecision]:
    """Classify a single batch of lines. Returns list of decisions.

    On JSON parse failure, splits the batch in half and retries each half
    recursively. If a batch of 1 line still fails, returns an empty list
    for that line (it will be treated as 'uncertain' by the caller).
    """
    import json as _json

    if not lines:
        return []

    numbered = "\n".join(
        f"{absolute_start + i}: {line}" for i, line in enumerate(lines)
    )
    user_prompt = build_user_prompt(numbered)

    try:
        raw = engine.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1536,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.warning(f"Batch at line {absolute_start} generation failed: {e}")
        raw = ""

    decisions: list[LineDecision] = []
    parse_ok = False

    if raw:
        try:
            parsed = _json.loads(raw)
            decisions_raw = parsed.get("line_decisions", [])
            if isinstance(decisions_raw, list):
                for entry in decisions_raw:
                    try:
                        idx = int(entry["index"])
                        decisions.append(
                            LineDecision(
                                index=idx,
                                action=str(entry["action"]),
                                reason=str(entry.get("reason", "")),
                                confidence=str(entry.get("confidence", "medium")),
                            )
                        )
                    except (KeyError, TypeError, ValueError):
                        continue
                parse_ok = True
        except _json.JSONDecodeError as e:
            logger.warning(
                f"Batch at line {absolute_start} invalid JSON ({e}). "
                f"Retrying with smaller batch."
            )

    if parse_ok:
        return decisions

    # Fallback: split and retry, unless we're already at size 1
    if len(lines) <= 1:
        logger.warning(
            f"Single-line batch at {absolute_start} failed to parse; skipping."
        )
        return []

    mid = len(lines) // 2
    logger.warning(
        f"Batch at line {absolute_start} failed. Splitting {len(lines)} lines into "
        f"{mid} and {len(lines) - mid} and retrying."
    )
    left = _classify_batch(
        engine, lines[:mid], absolute_start, system_prompt, build_user_prompt
    )
    right = _classify_batch(
        engine,
        lines[mid:],
        absolute_start + mid,
        system_prompt,
        build_user_prompt,
    )
    return left + right


class Executor:
    def __init__(
        self,
        engine: LLMEngine | None = None,
        batch_size: int = 15,
    ) -> None:
        self._engine = engine or get_engine()
        self._batch_size = batch_size

    def classify_lines(
        self,
        text: str,
        user_instructions: str | None = None,
        document_type: str | None = None,
        progress_callback: callable | None = None,
    ) -> ExecutorResult:
        """Ask the model to classify each line of text, in batches.

        Long documents are split into batches of `batch_size` lines.
        Each batch is classified independently; results are merged with
        line indices offset to refer to the original document.

        Raises ValueError if every batch fails to produce usable JSON.
        """
        lines = text.split("\n")
        total_lines = len(lines)

        if total_lines == 0:
            return ExecutorResult(
                line_decisions=[],
                model_name=self._engine._filename,
                raw_response="",
            )

        all_decisions: list[LineDecision] = []
        raw_batches: list[str] = []
        batches_attempted = 0
        batches_succeeded = 0

        total_batches = (total_lines + self._batch_size - 1) // self._batch_size
        print(
            f"[LLM] Starting classification of {total_lines} lines in "
            f"{total_batches} batches (size {self._batch_size})."
        )

        if progress_callback:
            progress_callback(0, total_lines)

        # Compose the system prompt once, outside the batch loop.
        system_prompt = build_system_prompt(user_instructions, document_type)

        for start in range(0, total_lines, self._batch_size):
            end = min(start + self._batch_size, total_lines)
            batch_lines = lines[start:end]

            print(f"[LLM] Classifying batch lines {start}-{end} of {total_lines}...")

            batch_decisions = _classify_batch(
                engine=self._engine,
                lines=batch_lines,
                absolute_start=start,
                system_prompt=system_prompt,
                build_user_prompt=build_executor_user_prompt,
            )
            all_decisions.extend(batch_decisions)
            if batch_decisions:
                batches_succeeded += 1
            batches_attempted += 1
            if progress_callback:
                progress_callback(end, total_lines)

        if batches_succeeded == 0:
            raise ValueError(
                f"All {batches_attempted} batches failed. "
                f"First raw response: {raw_batches[0][:400] if raw_batches else '(none)'}"
            )

        # Deduplicate: if the model produced multiple decisions for the same
        # index (rare but possible), keep the first.
        seen: set[int] = set()
        unique_decisions: list[LineDecision] = []
        for d in all_decisions:
            if d.index in seen:
                continue
            seen.add(d.index)
            unique_decisions.append(d)

        return ExecutorResult(
            line_decisions=unique_decisions,
            model_name=self._engine._filename,
            raw_response="\n---BATCH---\n".join(raw_batches),
        )
