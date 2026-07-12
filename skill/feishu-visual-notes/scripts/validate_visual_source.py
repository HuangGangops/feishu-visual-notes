#!/usr/bin/env python3
"""Validate UTF-8 Feishu XML, highlights, and editable SVG safety."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


WHITEBOARD = re.compile(r'<whiteboard\s+[^>]*type=["\']svg["\'][^>]*>(.*?)</whiteboard>', re.I | re.S)
HIGHLIGHT = re.compile(r'<span\s+[^>]*background-color=["\'][^"\']+["\'][^>]*>(.*?)</span>', re.I | re.S)
HEADING = re.compile(r'<h[1-9]\b[^>]*>(.*?)</h[1-9]>', re.I | re.S)
PARAGRAPH = re.compile(r'<p\b[^>]*>(.*?)</p>', re.I | re.S)
TAGS = re.compile(r'<[^>]+>')
UNSUPPORTED = {
    "external image references": r"<image\b",
    "scripts": r"<script\b",
    "filters": r"<filter\b|\sfilter=",
    "masks": r"<mask\b|\smask=",
    "clip paths": r"<clipPath\b|\sclip-path=",
    "patterns": r"<pattern\b",
    "gradients": r"<(?:linear|radial)Gradient\b",
}


def plain_length(fragment: str) -> int:
    return len(re.sub(r"\s+", "", html.unescape(TAGS.sub("", fragment))))


def validate(path: Path, minimum_whiteboards: int, minimum_highlights: int, maximum_highlight_ratio: float) -> dict[str, object]:
    content = path.read_text(encoding="utf-8", errors="strict")
    errors: list[str] = []
    boards = WHITEBOARD.findall(content)
    svg_content = "\n".join(boards)
    document = WHITEBOARD.sub("", content)
    highlights = HIGHLIGHT.findall(document)
    body_length = plain_length(document)
    highlight_length = sum(plain_length(value) for value in highlights)
    ratio = highlight_length / body_length if body_length else 0.0
    if "\ufffd" in content:
        errors.append("The source contains Unicode replacement characters.")
    if re.search(r"\?{4,}", content):
        errors.append("The source contains four or more question marks and may have broken Chinese encoding.")
    if len(boards) < minimum_whiteboards:
        errors.append(f"Expected at least {minimum_whiteboards} SVG whiteboards but found {len(boards)}.")
    if len(highlights) < minimum_highlights:
        errors.append(f"Expected at least {minimum_highlights} highlights but found {len(highlights)}.")
    if ratio > maximum_highlight_ratio:
        errors.append(f"Highlighted text is {ratio:.2%}; the maximum is {maximum_highlight_ratio:.2%}.")
    for heading in HEADING.findall(document):
        if HIGHLIGHT.search(heading):
            errors.append("Headings must not contain inline background highlights.")
    for paragraph in PARAGRAPH.findall(document):
        length = plain_length(paragraph)
        highlighted = sum(plain_length(value) for value in HIGHLIGHT.findall(paragraph))
        if length and highlighted / length > 0.75:
            errors.append("More than three quarters of a paragraph is highlighted.")
    for label, pattern in UNSUPPORTED.items():
        if re.search(pattern, svg_content, re.I):
            errors.append(f"The source contains unsupported SVG {label}.")
    fragment = re.sub(r"^\s*<\?xml[^?]*\?>", "", content)
    try:
        ET.fromstring(f"<root>{fragment}</root>")
    except ET.ParseError as exc:
        errors.append(f"The source is not a well-formed Feishu XML fragment: {exc}")
    return {
        "ok": not errors,
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "svg_whiteboards": len(boards),
        "inline_highlights": len(highlights),
        "highlight_chars": highlight_length,
        "highlight_ratio": round(ratio, 4),
        "errors": sorted(set(errors)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--minimum-whiteboards", type=int, default=0)
    parser.add_argument("--minimum-highlights", type=int, default=0)
    parser.add_argument("--maximum-highlight-ratio", type=float, default=0.30)
    args = parser.parse_args()
    try:
        result = validate(args.input, args.minimum_whiteboards, args.minimum_highlights, args.maximum_highlight_ratio)
    except (OSError, UnicodeError) as exc:
        result = {"ok": False, "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
