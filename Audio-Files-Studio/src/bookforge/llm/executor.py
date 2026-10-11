"""Executor: runs a classification pass against a local LLM."""

from __future__ import annotations

import json
import logging

from .engine import LLMEngine, get_engine
from .prompts import EXECUTOR_SYSTEM_PROMPT, build_executor_user_prompt
from .schemas import ExecutorResult, LineDecision

logger = logging.getLogger("bookforge.llm.executor")


class Executor:
    def __init__(
        self,
        engine: LLMEngine | None = None,
        batch_size: int = 50,
    ) -> None:
        self._engine = engine or get_engine()
        self._batch_size = batch_size

    def classify_lines(self, text: str) -> ExecutorResult:
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

        for start in range(0, total_lines, self._batch_size):
            end = min(start + self._batch_size, total_lines)
            batch_lines = lines[start:end]
            batches_attempted += 1

            # Number lines within the batch starting at 0, but the LLM sees
            # absolute indices so its decisions line up with the document.
            numbered = "\n".join(f"{start + i}: {line}" for i, line in enumerate(batch_lines))
            user_prompt = build_executor_user_prompt(numbered)

            try:
                raw = self._engine.generate(
                    system_prompt=EXECUTOR_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    max_tokens=2048,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
            except Exception as e:
                logger.warning(f"Batch {start}-{end} failed during generation: {e}")
                continue

            raw_batches.append(raw)

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Batch {start}-{end} returned invalid JSON: {e}. First 200 chars: {raw[:200]}"
                )
                continue

            decisions_raw = parsed.get("line_decisions")
            if not isinstance(decisions_raw, list):
                logger.warning(
                    f"Batch {start}-{end} missing 'line_decisions' array. "
                    f"Got keys: {list(parsed.keys())}"
                )
                continue

            for entry in decisions_raw:
                try:
                    idx = int(entry["index"])
                    # Sanity: reject out-of-range indices.
                    if idx < 0 or idx >= total_lines:
                        logger.warning(f"Skipping out-of-range index {idx}")
                        continue
                    all_decisions.append(
                        LineDecision(
                            index=idx,
                            action=str(entry["action"]),
                            reason=str(entry.get("reason", "")),
                            confidence=str(entry.get("confidence", "medium")),
                        )
                    )
                except (KeyError, TypeError, ValueError) as e:
                    logger.warning(f"Skipping malformed decision entry: {entry} ({e})")

            batches_succeeded += 1

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
