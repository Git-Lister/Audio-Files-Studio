"""CLI verification for the LLM engine.

Usage (inside the container):
    python -m bookforge.llm
"""

from __future__ import annotations

import json
import sys

from .executor import Executor

SAMPLE_TEXT = """Philosophia (2026) 54:379 - 396

Bees, Humans and Robots: Ethical and Epistemic Implications of Biohybridity

Jarek Kaminski1 · Joanna Ziemna1

Abstract This article explores the ethical, cognitive, and epistemic stakes of introducing smart-hive technologies.

1 Introduction

In an era of rapid technological advancement, new alliances between nature and technology are appearing with increasing frequency.

jarek.kaminski@amu.edu.pl

Philosophia (2026) 54:379 - 396

The case discussed here - collaborations between honeybee colonies - belongs to this expanding field.
"""


def main() -> int:
    print("Loading model and running classification on sample text...")
    print(f"Sample: {len(SAMPLE_TEXT)} chars, {len(SAMPLE_TEXT.splitlines())} lines")
    print()

    try:
        executor = Executor()
        result = executor.classify_lines(SAMPLE_TEXT)
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1

    print(f"Model: {result.model_name}")
    print(f"Decisions: {len(result.line_decisions)}")
    print()
    for d in result.line_decisions:
        print(f"  line {d.index:>3}: {d.action:<10} ({d.confidence}) — {d.reason}")

    # Sanity: at least one "remove" decision on this deliberately dirty sample.
    actions = [d.action for d in result.line_decisions]
    if "remove" not in actions:
        print()
        print("WARNING: no 'remove' decisions produced. Model may not be classifying "
              "the sample as expected.", file=sys.stderr)
        return 2

    print()
    print("OK: valid JSON, at least one line classified for removal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())