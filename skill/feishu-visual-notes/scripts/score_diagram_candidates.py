#!/usr/bin/env python3
"""Rank diagram types from explicit semantic relationship signals."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


SIGNALS: dict[str, list[tuple[str, int, str]]] = {
    "ordered_steps": [("flow", 7, "ordered stages")],
    "iteration": [("flow", 9, "closed feedback loop")],
    "roles": [("swimlane", 7, "multiple responsible roles")],
    "handoffs": [("swimlane", 9, "cross-role handoffs"), ("flow", 2, "ordered handoffs")],
    "progressive_narrowing": [("funnel", 10, "progressive filtering or conversion")],
    "two_axes": [("quadrant", 10, "classification by two independent dimensions")],
    "root_causes": [("cause-effect", 10, "causes converging on one outcome")],
    "conditional_paths": [("decision", 10, "conditional branch selection")],
    "comparison_dimensions": [("matrix", 10, "multi-dimensional comparison")],
    "chronology": [("timeline", 10, "time-ordered events")],
    "hierarchy": [("knowledge-map", 9, "parent-child hierarchy")],
    "central_topic": [("knowledge-map", 8, "one center with related branches")],
    "text_sufficient": [("prose", 12, "relationship is clearer as concise prose")],
    "table_sufficient": [("table", 12, "relationship is clearer as a table")],
}

VARIANTS = {
    "flow": "auto",
    "swimlane": "lanes",
    "funnel": "descending",
    "quadrant": "2x2",
    "cause-effect": "fishbone",
    "decision": "branch",
    "matrix": "comparison",
    "timeline": "auto",
    "knowledge-map": "auto",
    "prose": None,
    "table": None,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args()

    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1

    signals = data.get("signals") if isinstance(data, dict) else None
    if not isinstance(signals, list) or not signals:
        print(json.dumps({"ok": False, "errors": ["Input requires a non-empty signals array."]}, ensure_ascii=False, indent=2))
        return 1
    unknown = sorted({signal for signal in signals if signal not in SIGNALS})
    if unknown:
        print(json.dumps({"ok": False, "errors": ["Unknown signals: " + ", ".join(unknown)]}, ensure_ascii=False, indent=2))
        return 1

    scores: dict[str, int] = defaultdict(int)
    reasons: dict[str, list[str]] = defaultdict(list)
    for signal in signals:
        for diagram_type, points, reason in SIGNALS[signal]:
            scores[diagram_type] += points
            reasons[diagram_type].append(reason)

    ranked = sorted(scores, key=lambda item: (-scores[item], item))
    candidates = [
        {
            "type": diagram_type,
            "variant": "loop" if diagram_type == "flow" and "iteration" in signals else VARIANTS[diagram_type],
            "score": scores[diagram_type],
            "reasons": reasons[diagram_type],
        }
        for diagram_type in ranked[: max(1, args.top)]
    ]
    recommended = candidates[0]
    result = {
        "ok": True,
        "question": data.get("question", ""),
        "signals": signals,
        "decision": "reject-diagram" if recommended["type"] in {"prose", "table"} else "use-diagram",
        "recommended": recommended,
        "candidates": candidates,
        "margin": recommended["score"] - (candidates[1]["score"] if len(candidates) > 1 else 0),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
