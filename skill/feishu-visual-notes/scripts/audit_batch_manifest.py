#!/usr/bin/env python3
"""Audit page coverage and batch outputs before merging a long course source."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def page_set(value: object, field: str, total_pages: int, errors: list[str]) -> set[int]:
    if value is None:
        return set()
    if not isinstance(value, list) or any(not isinstance(page, int) for page in value):
        errors.append(f"{field} must be an array of page numbers.")
        return set()
    invalid = sorted({page for page in value if page < 1 or page > total_pages})
    if invalid:
        errors.append(f"{field} contains out-of-range pages: {invalid}")
    return {page for page in value if 1 <= page <= total_pages}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    total_pages = data.get("total_pages") if isinstance(data, dict) else None
    batches = data.get("batches") if isinstance(data, dict) else None
    if not isinstance(total_pages, int) or total_pages < 1:
        print(json.dumps({"ok": False, "errors": ["total_pages must be a positive integer."]}, ensure_ascii=False, indent=2))
        return 1
    if not isinstance(batches, list) or not batches:
        print(json.dumps({"ok": False, "errors": ["batches must be a non-empty array."]}, ensure_ascii=False, indent=2))
        return 1

    manifest_dir = args.input.resolve().parent
    coverage: list[int] = []
    incomplete: list[str] = []
    missing_outputs: list[str] = []
    for index, batch in enumerate(batches, start=1):
        if not isinstance(batch, dict):
            errors.append(f"batches[{index}] must be an object.")
            continue
        batch_id = str(batch.get("id", index))
        start = batch.get("start")
        end = batch.get("end")
        if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start or end > total_pages:
            errors.append(f"Batch {batch_id} has invalid page range: {start}-{end}.")
            continue
        coverage.extend(range(start, end + 1))
        if batch.get("status") != "complete":
            incomplete.append(batch_id)
        output = batch.get("output")
        if not isinstance(output, str) or not output.strip():
            missing_outputs.append(batch_id)
        elif not (manifest_dir / output).is_file():
            missing_outputs.append(batch_id)

    counts = Counter(coverage)
    missing_pages = [page for page in range(1, total_pages + 1) if counts[page] == 0]
    overlapping_pages = [page for page, count in counts.items() if count > 1]
    if missing_pages:
        errors.append(f"Missing pages: {missing_pages}")
    if overlapping_pages:
        errors.append(f"Pages assigned to multiple batches: {overlapping_pages}")
    if incomplete:
        (errors if args.strict else warnings).append("Incomplete batches: " + ", ".join(incomplete))
    if missing_outputs:
        (errors if args.strict else warnings).append("Missing batch output files: " + ", ".join(missing_outputs))

    uncertain = page_set(data.get("uncertain_pages"), "uncertain_pages", total_pages, errors)
    important = page_set(data.get("important_visual_pages"), "important_visual_pages", total_pages, errors)
    inspected = page_set(data.get("original_resolution_pages"), "original_resolution_pages", total_pages, errors)
    uninspected_uncertain = sorted(uncertain - inspected)
    uninspected_important = sorted(important - inspected)
    if uninspected_uncertain:
        errors.append(f"Uncertain pages not checked at original resolution: {uninspected_uncertain}")
    if uninspected_important:
        errors.append(f"Important visual pages not checked at original resolution: {uninspected_important}")

    duplicates = data.get("duplicates", [])
    if not isinstance(duplicates, list):
        errors.append("duplicates must be an array.")
    else:
        for index, group in enumerate(duplicates, start=1):
            if not isinstance(group, dict):
                errors.append(f"duplicates[{index}] must be an object.")
                continue
            pages = group.get("pages")
            canonical = group.get("canonical")
            if not isinstance(pages, list) or len(pages) < 2 or any(not isinstance(page, int) for page in pages):
                errors.append(f"duplicates[{index}].pages must contain at least two page numbers.")
            elif canonical not in pages:
                errors.append(f"duplicates[{index}].canonical must be one of its pages.")

    result = {
        "ok": not errors,
        "manifest": str(args.input.resolve()),
        "total_pages": total_pages,
        "batch_count": len(batches),
        "covered_pages": len(counts),
        "missing_pages": missing_pages,
        "overlapping_pages": overlapping_pages,
        "uncertain_pages": sorted(uncertain),
        "important_visual_pages": sorted(important),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
