"""Executor: runs a classification pass against a local LLM."""

from __future__ import annotations

import json
import logging

from .engine import LLMEngine, get_engine
from .prompts import EXECUTOR_SYSTEM_PROMPT, build_executor_user_prompt
from .schemas import ExecutorResult, LineDecision

logger = logging.getLogger("bookforge.llm.executor")


class Executor:
    def __init__(self, engine: LLMEngine | None = None) -> None:
        self._engine = engine or get_engine()

    def classify_lines(self, text: str) -> ExecutorResult:
        """Ask the model to classify each line of text.

        Raises ValueError if the model response is not valid JSON matching
        the expected schema.
        """
        lines = text.split("\n")
        numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(lines))
        user_prompt = build_executor_user_prompt(numbered)

        raw = self._engine.generate(
            system_prompt=EXECUTOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=4096,
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Model returned invalid JSON: {e}\nRaw: {raw[:400]}") from e

        decisions_raw = parsed.get("line_decisions")
        if not isinstance(decisions_raw, list):
            raise ValueError(f"JSON missing 'line_decisions' array. Got: {list(parsed.keys())}")

        decisions: list[LineDecision] = []
        for entry in decisions_raw:
            try:
                decisions.append(
                    LineDecision(
                        index=int(entry["index"]),
                        action=str(entry["action"]),
                        reason=str(entry.get("reason", "")),
                        confidence=str(entry.get("confidence", "medium")),
                    )
                )
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed decision entry: {entry} ({e})")

        return ExecutorResult(
            line_decisions=decisions,
            model_name=self._engine._filename,
            raw_response=raw,
        )