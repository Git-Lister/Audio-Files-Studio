"""Data structures for structured LLM output."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LineDecision:
    index: int
    action: str  # one of: "keep", "remove", "heading", "uncertain"
    reason: str = ""
    confidence: str = "medium"  # "high", "medium", "low"


@dataclass
class ExecutorResult:
    line_decisions: list[LineDecision] = field(default_factory=list)
    model_name: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_response: str = ""