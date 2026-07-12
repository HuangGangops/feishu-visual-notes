#!/usr/bin/env python3
"""Statically validate SVG layout before inserting it into a Feishu whiteboard."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

UNSUPPORTED_TAGS = {"filter", "mask", "clipPath", "pattern", "linearGradient", "radialGradient", "script", "image"}
UNSUPPORTED_ATTRIBUTES = {"filter", "mask", "clip-path"}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_number(value: str | None, default: float | None = None) -> float | None:
    if value is None:
        return default
    match = re.match(r"^\s*(-?\d+(?:\.\d+)?)", value)
    return float(match.group(1)) if match else default


def display_units(text: str) -> float:
    total = 0.0
    for char in text:
        if char.isspace():
            total += 0.35
        elif unicodedata.east_asian_width(char) in {"W", "F", "A"}:
            total += 1.0
        else:
            total += 0.58
    return total


def parse_source(path: Path) -> list[ET.Element]:
    content = path.read_text(encoding="utf-8")
    content = re.sub(r"^\s*<\?xml[^?]*\?>", "", content)
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        root = ET.fromstring(f"<root>{content}</root>")
    if local_name(root.tag) == "svg":
        return [root]
    return [element for element in root.iter() if local_name(element.tag) == "svg"]


def rect_bounds(element: ET.Element) -> tuple[float, float, float, float] | None:
    x = parse_number(element.get("x"), 0)
    y = parse_number(element.get("y"), 0)
    width = parse_number(element.get("width"))
    height = parse_number(element.get("height"))
    if width is None or height is None:
        return None
    return x, y, x + width, y + height


def shape_bounds(element: ET.Element) -> tuple[float, float, float, float] | None:
    name = local_name(element.tag)
    if name == "rect":
        return rect_bounds(element)
    if name == "circle":
        cx = parse_number(element.get("cx"), 0)
        cy = parse_number(element.get("cy"), 0)
        radius = parse_number(element.get("r"))
        if radius is None:
            return None
        return cx - radius, cy - radius, cx + radius, cy + radius
    if name == "ellipse":
        cx = parse_number(element.get("cx"), 0)
        cy = parse_number(element.get("cy"), 0)
        rx = parse_number(element.get("rx"))
        ry = parse_number(element.get("ry"))
        if rx is None or ry is None:
            return None
        return cx - rx, cy - ry, cx + rx, cy + ry
    if name in {"polygon", "polyline"}:
        values = [parse_number(value) for value in element.get("points", "").replace(",", " ").split()]
        if len(values) < 4 or len(values) % 2 or any(value is None for value in values):
            return None
        xs = [float(value) for value in values[0::2]]
        ys = [float(value) for value in values[1::2]]
        return min(xs), min(ys), max(xs), max(ys)
    if name == "line":
        x1, y1 = parse_number(element.get("x1"), 0), parse_number(element.get("y1"), 0)
        x2, y2 = parse_number(element.get("x2"), 0), parse_number(element.get("y2"), 0)
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
    return None


def text_bounds(element: ET.Element) -> tuple[float, float, float, float] | None:
    x = parse_number(element.get("x"))
    y = parse_number(element.get("y"))
    size = parse_number(element.get("font-size"))
    if x is None or y is None or size is None:
        return None
    text = "".join(element.itertext()).strip()
    width = display_units(text) * size * 0.96
    anchor = element.get("text-anchor", "start")
    if anchor == "middle":
        left, right = x - width / 2, x + width / 2
    elif anchor == "end":
        left, right = x - width, x
    else:
        left, right = x, x + width
    return left, y - size, right, y + size * 0.28


def overlaps(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> bool:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    return right - left > 2 and bottom - top > 2


def inside(inner: tuple[float, float, float, float], outer: tuple[float, float, float, float], tolerance: float = 0) -> bool:
    return (
        inner[0] >= outer[0] - tolerance
        and inner[1] >= outer[1] - tolerance
        and inner[2] <= outer[2] + tolerance
        and inner[3] <= outer[3] + tolerance
    )


def validate_svg(svg: ET.Element, index: int) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    prefix = f"svg[{index}]"
    view_box = svg.get("viewBox")
    if not view_box:
        return {"errors": [f"{prefix}: missing viewBox"], "warnings": [], "nodes": 0, "texts": 0}
    parts = [parse_number(value) for value in view_box.replace(",", " ").split()]
    if len(parts) != 4 or any(value is None for value in parts):
        return {"errors": [f"{prefix}: invalid viewBox '{view_box}'"], "warnings": [], "nodes": 0, "texts": 0}
    min_x, min_y, width, height = (float(value) for value in parts)
    canvas = (min_x, min_y, min_x + width, min_y + height)
    if width < 1000 or height < 600:
        warnings.append(f"{prefix}: canvas is smaller than the recommended 1600 x 900 working area")

    parent_shapes: dict[str, tuple[float, float, float, float]] = {}
    node_count = 0
    text_records: list[tuple[ET.Element, tuple[float, float, float, float]]] = []
    parent_texts: dict[str, list[tuple[ET.Element, tuple[float, float, float, float]]]] = {}
    content_bounds: list[tuple[float, float, float, float]] = []

    for element in svg.iter():
        name = local_name(element.tag)
        if name in UNSUPPORTED_TAGS:
            errors.append(f"{prefix}: unsupported SVG element <{name}>")
        for attribute in UNSUPPORTED_ATTRIBUTES:
            if attribute in element.attrib:
                errors.append(f"{prefix}: unsupported SVG attribute '{attribute}'")
        transform = element.get("transform", "")
        if re.search(r"\b(?:skewX|skewY|matrix)\s*\(", transform):
            warnings.append(f"{prefix}: transform '{transform}' may degrade editability")

        bounds = shape_bounds(element)
        element_id = element.get("id")
        if bounds and element.get("data-role") != "canvas":
            content_bounds.append(bounds)
        if bounds and element_id:
            parent_shapes[element_id] = bounds
        if element.get("data-role") == "node":
            node_count += 1
            if bounds and not inside(bounds, canvas, 1):
                errors.append(f"{prefix}: node '{element_id or node_count}' is outside the canvas")

        if name == "text":
            size = parse_number(element.get("font-size"))
            if size is None:
                errors.append(f"{prefix}: text is missing font-size")
                continue
            if size < 20:
                errors.append(f"{prefix}: text '{''.join(element.itertext())[:24]}' uses font-size {size:g}, below 20")
            bounds = text_bounds(element)
            if not bounds:
                errors.append(f"{prefix}: text has invalid x/y coordinates")
                continue
            if not inside(bounds, canvas, 4):
                errors.append(f"{prefix}: text '{''.join(element.itertext())[:24]}' extends outside the canvas")
            content_bounds.append(bounds)
            text_records.append((element, bounds))
            parent_id = element.get("data-parent")
            if parent_id:
                parent_texts.setdefault(parent_id, []).append((element, bounds))

    diagram_type = svg.get("data-diagram-type", "")
    max_nodes = {"swimlane": 20, "funnel": 6, "cause-effect": 7}.get(diagram_type, 7)
    if node_count > max_nodes:
        errors.append(f"{prefix}: contains {node_count} primary nodes; maximum for {diagram_type or 'this diagram'} is {max_nodes}")

    for parent_id, records in parent_texts.items():
        parent_bounds = parent_shapes.get(parent_id)
        if not parent_bounds:
            errors.append(f"{prefix}: text references missing parent '{parent_id}'")
            continue
        for element, bounds in records:
            if not inside(bounds, parent_bounds, 8):
                errors.append(f"{prefix}: text '{''.join(element.itertext())[:24]}' overflows parent '{parent_id}'")
        for first_index, (_, first_bounds) in enumerate(records):
            for _, second_bounds in records[first_index + 1:]:
                if overlaps(first_bounds, second_bounds):
                    errors.append(f"{prefix}: text lines overlap inside parent '{parent_id}'")
                    break

    width_ratio = 0.0
    height_ratio = 0.0
    center_offset = 0.0
    if content_bounds:
        content_box = (
            min(item[0] for item in content_bounds),
            min(item[1] for item in content_bounds),
            max(item[2] for item in content_bounds),
            max(item[3] for item in content_bounds),
        )
        width_ratio = (content_box[2] - content_box[0]) / width
        height_ratio = (content_box[3] - content_box[1]) / height
        content_center_x = (content_box[0] + content_box[2]) / 2
        content_center_y = (content_box[1] + content_box[3]) / 2
        canvas_center_x = min_x + width / 2
        canvas_center_y = min_y + height / 2
        center_offset = max(abs(content_center_x - canvas_center_x) / width, abs(content_center_y - canvas_center_y) / height)
        if max(width_ratio, height_ratio) < 0.45:
            warnings.append(f"{prefix}: content uses less than 45% of both canvas dimensions")
        if center_offset > 0.16:
            warnings.append(f"{prefix}: content is visibly off-center within the canvas")

    for first_index, (first, first_bounds) in enumerate(text_records):
        if first.get("data-parent"):
            continue
        for second, second_bounds in text_records[first_index + 1:]:
            if second.get("data-parent"):
                continue
            if overlaps(first_bounds, second_bounds):
                warnings.append(
                    f"{prefix}: standalone text may overlap: '{''.join(first.itertext())[:16]}' and '{''.join(second.itertext())[:16]}'"
                )

    return {
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "nodes": node_count,
        "texts": len(text_records),
        "content_width_ratio": round(width_ratio, 4),
        "content_height_ratio": round(height_ratio, 4),
        "center_offset": round(center_offset, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Standalone SVG or Feishu XML fragment")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()

    path = Path(args.input)
    try:
        svgs = parse_source(path)
    except (OSError, UnicodeError, ET.ParseError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1
    if not svgs:
        print(json.dumps({"ok": False, "errors": ["No SVG elements found"]}, ensure_ascii=False, indent=2))
        return 1

    results = [validate_svg(svg, index) for index, svg in enumerate(svgs)]
    errors = [item for result in results for item in result["errors"]]
    warnings = [item for result in results for item in result["warnings"]]
    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "input": str(path.resolve()),
        "svg_count": len(svgs),
        "errors": errors,
        "warnings": warnings,
        "diagrams": results,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
