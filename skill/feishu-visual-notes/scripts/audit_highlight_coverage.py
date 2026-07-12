#!/usr/bin/env python3
"""Verify that a document's semantic highlight inventory is fully represented."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path


HIGHLIGHT_PATTERN = re.compile(
    r'<span\s+[^>]*background-color=["\'][^"\']+["\'][^>]*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")
PUNCTUATION_PATTERN = re.compile(r"[\s\W_]+", re.UNICODE)


def normalize(value: str) -> str:
    plain = TAG_PATTERN.sub("", html.unescape(value))
    normalized = unicodedata.normalize("NFKC", plain).lower()
    return PUNCTUATION_PATTERN.sub("", normalized)


def load_inventory(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_items = data.get("key_points") if isinstance(data, dict) else None
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("Inventory must contain a non-empty key_points array.")

    items: list[dict[str, object]] = []
    for index, item in enumerate(raw_items, start=1):
        if isinstance(item, str):
            item = {"highlight": item}
        if not isinstance(item, dict):
            raise ValueError(f"key_points[{index}] must be a string or object.")
        highlight = item.get("highlight", item.get("text"))
        if not isinstance(highlight, str) or not normalize(highlight):
            raise ValueError(f"key_points[{index}] requires non-empty highlight text.")
        items.append(
            {
                "highlight": highlight,
                "normalized": normalize(highlight),
                "section": item.get("section", ""),
                "required": item.get("required", True) is not False,
            }
        )
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    try:
        content = args.content.read_text(encoding="utf-8")
        items = load_inventory(args.inventory)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1

    actual_text = [TAG_PATTERN.sub("", html.unescape(match)) for match in HIGHLIGHT_PATTERN.findall(content)]
    actual_normalized = [normalize(value) for value in actual_text if normalize(value)]
    actual_counts = Counter(actual_normalized)
    expected_counts = Counter(str(item["normalized"]) for item in items if item["required"])
    inventory_counts = Counter(str(item["normalized"]) for item in items)

    errors: list[str] = []
    warnings: list[str] = []
    missing = [
        str(item["highlight"])
        for item in items
        if item["required"] and actual_counts[str(item["normalized"])] == 0
    ]
    duplicate_inventory = [key for key, count in Counter(str(item["normalized"]) for item in items).items() if count > 1]
    duplicate_highlights = [text for text, count in actual_counts.items() if count > 1]
    unexpected = [text for text in actual_text if normalize(text) not in inventory_counts]

    if missing:
        errors.append("Missing required highlights: " + " | ".join(missing))
    if duplicate_inventory:
        errors.append("Inventory contains duplicate key points: " + " | ".join(duplicate_inventory))
    if duplicate_highlights:
        errors.append("Document repeats highlighted key points: " + " | ".join(duplicate_highlights))
    if unexpected:
        message = "Highlights missing from inventory: " + " | ".join(unexpected)
        (errors if args.strict else warnings).append(message)

    result = {
        "ok": not errors,
        "content": str(args.content.resolve()),
        "inventory": str(args.inventory.resolve()),
        "required_key_points": sum(1 for item in items if item["required"]),
        "actual_highlights": len(actual_text),
        "matched_key_points": sum(1 for item in items if actual_counts[str(item["normalized"])] > 0),
        "missing": missing,
        "unexpected": unexpected,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
