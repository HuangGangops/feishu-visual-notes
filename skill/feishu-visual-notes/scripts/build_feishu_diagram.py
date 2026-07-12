#!/usr/bin/env python3
"""Build deterministic, editable SVG diagrams for Feishu whiteboards."""

from __future__ import annotations

import argparse
import json
import math
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

WIDTH = 1600
HEIGHT = 900
FONT = "Noto Sans SC, Microsoft YaHei, Arial"
PALETTE = {
    "blue": ("#E7F0FF", "#3370FF"),
    "green": ("#E8F8EF", "#2F9E62"),
    "orange": ("#FFF3DC", "#D97706"),
    "red": ("#FFE9EE", "#D9485F"),
    "purple": ("#F0EBFF", "#7C5CFC"),
    "gray": ("#EFF0F1", "#8F959E"),
}
ACCENTS = tuple(PALETTE)


class SpecError(ValueError):
    pass


def qname(name: str) -> str:
    return f"{{{SVG_NS}}}{name}"


def number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")


def add(parent: ET.Element, name: str, **attrs: Any) -> ET.Element:
    normalized = {key.replace("_", "-"): number(value) if isinstance(value, (int, float)) else str(value)
                  for key, value in attrs.items() if value is not None}
    return ET.SubElement(parent, qname(name), normalized)


def display_units(text: str) -> float:
    units = 0.0
    for char in text:
        if char.isspace():
            units += 0.35
        elif unicodedata.east_asian_width(char) in {"W", "F", "A"}:
            units += 1.0
        else:
            units += 0.58
    return units


def wrap_text(text: str, max_units: float, max_lines: int) -> list[str]:
    source = " ".join(str(text or "").strip().split())
    if not source:
        return []

    lines: list[str] = []
    current = ""
    for char in source:
        candidate = current + char
        if current and display_units(candidate) > max_units:
            lines.append(current.rstrip())
            current = char.lstrip()
        else:
            current = candidate
    if current:
        lines.append(current.rstrip())

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        tail = lines[-1]
        while tail and display_units(tail + "...") > max_units:
            tail = tail[:-1]
        lines[-1] = tail.rstrip() + "..."
    return lines


def normalize_node(value: Any, index: int, prefix: str = "node") -> dict[str, str]:
    if isinstance(value, str):
        return {"id": f"{prefix}-{index}", "title": value, "body": "", "accent": ACCENTS[index % len(ACCENTS)]}
    if not isinstance(value, dict):
        raise SpecError(f"{prefix} item {index + 1} must be a string or object")
    return {
        "id": str(value.get("id") or f"{prefix}-{index}"),
        "title": str(value.get("title") or value.get("label") or "").strip(),
        "body": str(value.get("body") or value.get("description") or value.get("result") or "").strip(),
        "accent": str(value.get("accent") or ACCENTS[index % len(ACCENTS)]),
        "parent": str(value.get("parent") or "").strip(),
        "meta": str(value.get("meta") or value.get("date") or "").strip(),
    }


def require_items(spec: dict[str, Any], key: str, minimum: int, maximum: int) -> list[Any]:
    items = spec.get(key)
    if not isinstance(items, list) or not minimum <= len(items) <= maximum:
        raise SpecError(f"{key} must contain {minimum}-{maximum} items")
    return items


def add_text_lines(
    parent: ET.Element,
    x: float,
    y: float,
    text: str,
    *,
    size: int,
    color: str = "#1F2329",
    weight: int = 500,
    anchor: str = "middle",
    max_units: float = 20,
    max_lines: int = 2,
    line_height: float | None = None,
    role: str = "text",
    parent_id: str | None = None,
) -> list[ET.Element]:
    lines = wrap_text(text, max_units, max_lines)
    step = line_height or size * 1.35
    elements = []
    for index, line in enumerate(lines):
        element = add(
            parent,
            "text",
            x=x,
            y=y + index * step,
            text_anchor=anchor,
            font_size=size,
            font_weight=weight,
            fill=color,
            font_family=FONT,
            data_role=role,
            data_parent=parent_id,
        )
        element.text = line
        elements.append(element)
    return elements


def add_card(
    parent: ET.Element,
    x: float,
    y: float,
    width: float,
    height: float,
    node: dict[str, str],
    *,
    node_id: str,
    role: str = "node",
    compact: bool = False,
) -> None:
    accent = node.get("accent", "blue")
    fill, stroke = PALETTE.get(accent, PALETTE["blue"])
    add(
        parent,
        "rect",
        id=node_id,
        x=x,
        y=y,
        width=width,
        height=height,
        rx=18,
        fill=fill,
        stroke=stroke,
        stroke_width=2,
        data_role=role,
    )
    max_units = max(6.0, (width - 36) / 25)
    if compact:
        add_text_lines(
            parent, x + width / 2, y + 34, node["title"], size=24, weight=700,
            max_units=max_units, max_lines=1, role="node-title", parent_id=node_id,
        )
        if node.get("body"):
            add_text_lines(
                parent, x + width / 2, y + 66, node["body"], size=20, color="#646A73",
                max_units=max_units * 1.15, max_lines=1, role="node-body", parent_id=node_id,
            )
        return

    title_lines = add_text_lines(
        parent, x + width / 2, y + 42, node["title"], size=25, weight=700,
        max_units=max_units, max_lines=2, line_height=31, role="node-title", parent_id=node_id,
    )
    body_y = y + 112 if len(title_lines) > 1 else y + 88
    if node.get("body"):
        add_text_lines(
            parent, x + width / 2, body_y, node["body"], size=20, color="#646A73",
            max_units=max_units * 1.15, max_lines=3, line_height=27, role="node-body", parent_id=node_id,
        )


def add_arrow(parent: ET.Element, x1: float, y1: float, x2: float, y2: float, color: str = "#8F959E") -> None:
    add(parent, "line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=color, stroke_width=4,
        stroke_linecap="round", data_role="connector")
    angle = math.atan2(y2 - y1, x2 - x1)
    length = 14
    spread = 7
    base_x = x2 - length * math.cos(angle)
    base_y = y2 - length * math.sin(angle)
    p1 = (base_x + spread * math.sin(angle), base_y - spread * math.cos(angle))
    p2 = (base_x - spread * math.sin(angle), base_y + spread * math.cos(angle))
    points = f"{number(x2)},{number(y2)} {number(p1[0])},{number(p1[1])} {number(p2[0])},{number(p2[1])}"
    add(parent, "polygon", points=points, fill=color, data_role="arrowhead")


def add_poly_arrow(parent: ET.Element, points: Iterable[tuple[float, float]], color: str = "#8F959E") -> None:
    point_list = list(points)
    add(parent, "polyline", points=" ".join(f"{number(x)},{number(y)}" for x, y in point_list),
        fill="none", stroke=color, stroke_width=4, stroke_linecap="round", stroke_linejoin="round",
        data_role="connector")
    (x1, y1), (x2, y2) = point_list[-2:]
    angle = math.atan2(y2 - y1, x2 - x1)
    length = 14
    spread = 7
    base_x = x2 - length * math.cos(angle)
    base_y = y2 - length * math.sin(angle)
    p1 = (base_x + spread * math.sin(angle), base_y - spread * math.cos(angle))
    p2 = (base_x - spread * math.sin(angle), base_y + spread * math.cos(angle))
    add(parent, "polygon", points=f"{number(x2)},{number(y2)} {number(p1[0])},{number(p1[1])} {number(p2[0])},{number(p2[1])}",
        fill=color, data_role="arrowhead")


def new_canvas(spec: dict[str, Any], diagram_type: str, variant: str) -> ET.Element:
    svg = ET.Element(qname("svg"), {
        "width": str(WIDTH),
        "height": str(HEIGHT),
        "viewBox": f"0 0 {WIDTH} {HEIGHT}",
        "data-diagram-type": diagram_type,
        "data-variant": variant,
    })
    add(svg, "rect", x=0, y=0, width=WIDTH, height=HEIGHT, fill="#F7F8FA", data_role="canvas")
    add_text_lines(svg, WIDTH / 2, 68, str(spec.get("title") or "Untitled diagram"), size=38,
                   weight=700, max_units=34, max_lines=1, role="diagram-title")
    if spec.get("subtitle"):
        add_text_lines(svg, WIDTH / 2, 108, str(spec["subtitle"]), size=22, color="#646A73",
                       max_units=55, max_lines=1, role="diagram-subtitle")
    return svg


def element_bounds(element: ET.Element) -> tuple[float, float, float, float] | None:
    name = element.tag.rsplit("}", 1)[-1]
    if name == "rect":
        x = float(element.get("x", 0))
        y = float(element.get("y", 0))
        return x, y, x + float(element.get("width", 0)), y + float(element.get("height", 0))
    if name == "circle":
        cx, cy, radius = float(element.get("cx", 0)), float(element.get("cy", 0)), float(element.get("r", 0))
        return cx - radius, cy - radius, cx + radius, cy + radius
    if name == "ellipse":
        cx, cy = float(element.get("cx", 0)), float(element.get("cy", 0))
        rx, ry = float(element.get("rx", 0)), float(element.get("ry", 0))
        return cx - rx, cy - ry, cx + rx, cy + ry
    if name == "line":
        x1, y1 = float(element.get("x1", 0)), float(element.get("y1", 0))
        x2, y2 = float(element.get("x2", 0)), float(element.get("y2", 0))
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
    if name in {"polyline", "polygon"}:
        values = [float(value) for value in element.get("points", "").replace(",", " ").split()]
        if len(values) < 4 or len(values) % 2:
            return None
        xs, ys = values[0::2], values[1::2]
        return min(xs), min(ys), max(xs), max(ys)
    if name == "text":
        x, y = float(element.get("x", 0)), float(element.get("y", 0))
        size = float(element.get("font-size", 20))
        width = display_units("".join(element.itertext())) * size * 0.96
        anchor = element.get("text-anchor", "start")
        if anchor == "middle":
            left, right = x - width / 2, x + width / 2
        elif anchor == "end":
            left, right = x - width, x
        else:
            left, right = x, x + width
        return left, y - size, right, y + size * 0.3
    return None


def diagram_bounds(svg: ET.Element) -> tuple[float, float, float, float]:
    bounds = []
    for element in svg.iter():
        if element.get("data-role") == "canvas":
            continue
        current = element_bounds(element)
        if current:
            bounds.append(current)
    if not bounds:
        return 0, 0, WIDTH, HEIGHT
    return (
        min(item[0] for item in bounds),
        min(item[1] for item in bounds),
        max(item[2] for item in bounds),
        max(item[3] for item in bounds),
    )


def shift_element(element: ET.Element, dx: float, dy: float) -> None:
    for attribute in ("x", "x1", "x2", "cx"):
        if attribute in element.attrib:
            element.set(attribute, number(float(element.get(attribute, 0)) + dx))
    for attribute in ("y", "y1", "y2", "cy"):
        if attribute in element.attrib:
            element.set(attribute, number(float(element.get(attribute, 0)) + dy))
    if "points" in element.attrib:
        values = [float(value) for value in element.get("points", "").replace(",", " ").split()]
        if len(values) % 2 == 0:
            shifted = []
            for index in range(0, len(values), 2):
                shifted.extend((values[index] + dx, values[index + 1] + dy))
            element.set("points", " ".join(number(value) for value in shifted))


def finalize_canvas(svg: ET.Element, spec: dict[str, Any]) -> ET.Element:
    canvas_mode = str(spec.get("canvas") or "auto").strip()
    if canvas_mode not in {"auto", "square", "wide"}:
        raise SpecError("canvas must be auto, square, or wide")
    if canvas_mode == "wide":
        svg.set("data-canvas", "wide")
        return svg

    min_x, min_y, max_x, max_y = diagram_bounds(svg)
    target = 1600
    dx = target / 2 - (min_x + max_x) / 2
    dy = target / 2 - (min_y + max_y) / 2
    for child in list(svg):
        if child.get("data-role") == "canvas":
            child.set("height", str(target))
            continue
        for element in child.iter():
            shift_element(element, dx, dy)

    svg.set("height", str(target))
    svg.set("viewBox", f"0 0 {target} {target}")
    svg.set("data-canvas", "square")
    return svg


def select_variant(spec: dict[str, Any]) -> str:
    diagram_type = str(spec.get("type") or "").strip()
    requested = str(spec.get("variant") or "auto").strip()
    allowed = {
        "flow": {"auto", "horizontal", "vertical", "loop"},
        "knowledge-map": {"auto", "radial", "layered"},
        "timeline": {"auto", "linear", "alternating"},
        "matrix": {"auto", "comparison"},
        "decision": {"auto", "branch"},
        "swimlane": {"auto", "lanes"},
        "funnel": {"auto", "descending"},
        "quadrant": {"auto", "2x2"},
        "cause-effect": {"auto", "fishbone"},
    }
    if diagram_type not in allowed:
        raise SpecError(f"Unsupported diagram type: {diagram_type}")
    if requested not in allowed[diagram_type]:
        raise SpecError(f"Unsupported variant '{requested}' for type '{diagram_type}'")
    if requested != "auto":
        return requested
    if diagram_type == "flow":
        if spec.get("closed_loop"):
            return "loop"
        return "horizontal" if len(spec.get("nodes") or []) <= 5 else "vertical"
    if diagram_type == "knowledge-map":
        return "layered" if spec.get("levels") else "radial"
    if diagram_type == "timeline":
        return "linear" if len(spec.get("events") or []) <= 4 else "alternating"
    if diagram_type == "matrix":
        return "comparison"
    if diagram_type == "decision":
        return "branch"
    if diagram_type == "swimlane":
        return "lanes"
    if diagram_type == "funnel":
        return "descending"
    if diagram_type == "quadrant":
        return "2x2"
    return "fishbone"


def render_flow(spec: dict[str, Any], variant: str) -> ET.Element:
    raw_nodes = require_items(spec, "nodes", 2 if variant != "loop" else 3, 7)
    nodes = [normalize_node(value, index) for index, value in enumerate(raw_nodes)]
    svg = new_canvas(spec, "flow", variant)

    if variant == "horizontal":
        gap = 32
        node_width = min(260.0, (1472 - gap * (len(nodes) - 1)) / len(nodes))
        total = node_width * len(nodes) + gap * (len(nodes) - 1)
        x0 = (WIDTH - total) / 2
        y, height = 340, 210
        for index in range(len(nodes) - 1):
            x1 = x0 + (index + 1) * node_width + index * gap
            x2 = x1 + gap - 6
            add_arrow(svg, x1, y + height / 2, x2, y + height / 2)
        for index, node in enumerate(nodes):
            add_card(svg, x0 + index * (node_width + gap), y, node_width, height, node,
                     node_id=f"flow-node-{index}")
        return svg

    if variant == "vertical":
        width, height, gap = 620, 86, 18
        total = height * len(nodes) + gap * (len(nodes) - 1)
        y0 = max(140, (HEIGHT - total) / 2 + 35)
        x = (WIDTH - width) / 2
        for index in range(len(nodes) - 1):
            y1 = y0 + (index + 1) * height + index * gap
            add_arrow(svg, WIDTH / 2, y1, WIDTH / 2, y1 + gap - 5)
        for index, node in enumerate(nodes):
            add_card(svg, x, y0 + index * (height + gap), width, height, node,
                     node_id=f"flow-node-{index}", compact=True)
        return svg

    center_x, center_y = WIDTH / 2, 500
    radius_x, radius_y = 510, 270
    card_width, card_height = 250, 118
    centers = []
    for index in range(len(nodes)):
        angle = -math.pi / 2 + 2 * math.pi * index / len(nodes)
        centers.append((center_x + radius_x * math.cos(angle), center_y + radius_y * math.sin(angle)))
    for index, (x1, y1) in enumerate(centers):
        x2, y2 = centers[(index + 1) % len(centers)]
        dx, dy = x2 - x1, y2 - y1
        distance = math.hypot(dx, dy)
        shorten = min(145, distance * 0.3)
        start = (x1 + dx / distance * shorten, y1 + dy / distance * shorten)
        end = (x2 - dx / distance * shorten, y2 - dy / distance * shorten)
        add_arrow(svg, *start, *end)
    for index, (node, (cx, cy)) in enumerate(zip(nodes, centers)):
        add_card(svg, cx - card_width / 2, cy - card_height / 2, card_width, card_height, node,
                 node_id=f"flow-node-{index}", compact=True)
    add_text_lines(svg, center_x, center_y + 8, str(spec.get("center_label") or "持续迭代"), size=28,
                   weight=700, color="#3370FF", max_units=10, max_lines=1, role="center-label")
    return svg


def render_knowledge_map(spec: dict[str, Any], variant: str) -> ET.Element:
    center = normalize_node(spec.get("center") or "核心主题", 0, "center")
    svg = new_canvas(spec, "knowledge-map", variant)

    if variant == "radial":
        raw_branches = require_items(spec, "branches", 3, 7)
        branches = [normalize_node(value, index, "branch") for index, value in enumerate(raw_branches)]
        center_x, center_y = WIDTH / 2, 500
        radius_x, radius_y = 520, 270
        centers = []
        for index in range(len(branches)):
            angle = -math.pi / 2 + 2 * math.pi * index / len(branches)
            centers.append((center_x + radius_x * math.cos(angle), center_y + radius_y * math.sin(angle)))
        for cx, cy in centers:
            dx, dy = cx - center_x, cy - center_y
            distance = math.hypot(dx, dy)
            add_arrow(svg, center_x + dx / distance * 150, center_y + dy / distance * 75,
                      cx - dx / distance * 165, cy - dy / distance * 75, color="#9AA3B0")
        add_card(svg, center_x - 160, center_y - 75, 320, 150, center,
                 node_id="map-center", compact=False)
        for index, (branch, (cx, cy)) in enumerate(zip(branches, centers)):
            add_card(svg, cx - 145, cy - 65, 290, 130, branch,
                     node_id=f"map-branch-{index}", compact=True)
        return svg

    raw_levels = spec.get("levels")
    if not isinstance(raw_levels, list) or not 2 <= len(raw_levels) <= 4:
        raise SpecError("levels must contain 2-4 arrays for a layered knowledge map")
    levels: list[list[dict[str, str]]] = []
    for level_index, raw_level in enumerate(raw_levels):
        if not isinstance(raw_level, list) or not 1 <= len(raw_level) <= 5:
            raise SpecError("each knowledge-map level must contain 1-5 nodes")
        levels.append([normalize_node(value, index, f"level-{level_index}") for index, value in enumerate(raw_level)])

    level_height = 120
    y_positions = [170 + index * ((670 - level_height) / max(1, len(levels) - 1)) for index in range(len(levels))]
    positions: dict[str, tuple[float, float, float, float]] = {}
    for level_index, level in enumerate(levels):
        gap = 28
        width = min(290.0, (1400 - gap * (len(level) - 1)) / len(level))
        total = width * len(level) + gap * (len(level) - 1)
        x0 = (WIDTH - total) / 2
        for node_index, node in enumerate(level):
            positions[node["id"]] = (x0 + node_index * (width + gap), y_positions[level_index], width, level_height)

    for level_index in range(1, len(levels)):
        previous = levels[level_index - 1]
        for node_index, node in enumerate(levels[level_index]):
            parent_id = node.get("parent") or previous[min(node_index, len(previous) - 1)]["id"]
            if parent_id not in positions:
                parent_id = previous[0]["id"]
            px, py, pw, ph = positions[parent_id]
            x, y, width, _ = positions[node["id"]]
            add_poly_arrow(svg, [(px + pw / 2, py + ph), (px + pw / 2, y - 22), (x + width / 2, y - 22), (x + width / 2, y - 5)])

    for level in levels:
        for node in level:
            x, y, width, height = positions[node["id"]]
            add_card(svg, x, y, width, height, node, node_id=node["id"], compact=True)
    return svg


def render_timeline(spec: dict[str, Any], variant: str) -> ET.Element:
    raw_events = require_items(spec, "events", 2, 7)
    events = [normalize_node(value, index, "event") for index, value in enumerate(raw_events)]
    svg = new_canvas(spec, "timeline", variant)
    start_x, end_x, line_y = 150, 1450, 475
    add(svg, "line", x1=start_x, y1=line_y, x2=end_x, y2=line_y, stroke="#8F959E", stroke_width=5,
        stroke_linecap="round", data_role="timeline-axis")
    spacing = (end_x - start_x) / max(1, len(events) - 1)
    card_width = min(250.0, spacing - 24 if len(events) > 1 else 250)
    card_height = 170
    for index, event in enumerate(events):
        x = start_x + index * spacing
        is_top = variant == "linear" or index % 2 == 0
        card_y = 235 if is_top else 565
        marker_y = line_y
        add(svg, "line", x1=x, y1=marker_y, x2=x, y2=card_y + card_height if is_top else card_y,
            stroke="#B7BDC5", stroke_width=3, data_role="timeline-connector")
        add(svg, "circle", cx=x, cy=marker_y, r=13, fill="#3370FF", stroke="#FFFFFF", stroke_width=4,
            data_role="timeline-marker")
        if event.get("meta"):
            add_text_lines(svg, x, marker_y + (38 if is_top else -28), event["meta"], size=20, color="#3370FF",
                           weight=700, max_units=12, max_lines=1, role="timeline-meta")
        add_card(svg, x - card_width / 2, card_y, card_width, card_height, event,
                 node_id=f"timeline-event-{index}")
    return svg


def render_matrix(spec: dict[str, Any], variant: str) -> ET.Element:
    columns = require_items(spec, "columns", 2, 4)
    rows = require_items(spec, "rows", 1, 5)
    svg = new_canvas(spec, "matrix", variant)
    x0, y0, table_width, table_height = 90, 175, 1420, 650
    column_width = table_width / len(columns)
    row_height = table_height / (len(rows) + 1)

    for column_index, column in enumerate(columns):
        cell_id = f"matrix-header-{column_index}"
        x = x0 + column_index * column_width
        add(svg, "rect", id=cell_id, x=x, y=y0, width=column_width, height=row_height, rx=10,
            fill="#E7F0FF", stroke="#A8C5FF", stroke_width=2, data_role="matrix-cell")
        add_text_lines(svg, x + column_width / 2, y0 + row_height / 2 + 8, str(column), size=23, weight=700,
                       max_units=max(8, column_width / 25), max_lines=2, role="matrix-header", parent_id=cell_id)

    for row_index, row in enumerate(rows):
        if isinstance(row, dict):
            values = row.get("values")
            if values is None:
                values = [row.get(str(column), "") for column in columns]
        elif isinstance(row, list):
            values = row
        else:
            raise SpecError("each matrix row must be an array or object")
        if not isinstance(values, list) or len(values) != len(columns):
            raise SpecError("each matrix row must provide one value per column")
        for column_index, value in enumerate(values):
            cell_id = f"matrix-cell-{row_index}-{column_index}"
            x = x0 + column_index * column_width
            y = y0 + (row_index + 1) * row_height
            fill = "#EFF0F1" if column_index == 0 else ("#FFFFFF" if row_index % 2 == 0 else "#FAFBFC")
            add(svg, "rect", id=cell_id, x=x, y=y, width=column_width, height=row_height, rx=8,
                fill=fill, stroke="#D9DCE0", stroke_width=2, data_role="matrix-cell")
            add_text_lines(svg, x + column_width / 2, y + row_height / 2 - 12, str(value),
                           size=21 if column_index else 22, weight=700 if column_index == 0 else 500,
                           color="#1F2329" if column_index == 0 else "#42464D",
                           max_units=max(8, column_width / 23), max_lines=3, line_height=27,
                           role="matrix-text", parent_id=cell_id)
    return svg


def render_decision(spec: dict[str, Any], variant: str) -> ET.Element:
    options_raw = require_items(spec, "options", 2, 4)
    question = normalize_node(spec.get("question") or "如何选择？", 0, "question")
    options = [normalize_node(value, index, "option") for index, value in enumerate(options_raw)]
    svg = new_canvas(spec, "decision", variant)
    question_x, question_y, question_width, question_height = 520, 190, 560, 170
    gap = 34
    option_width = min(320.0, (1400 - gap * (len(options) - 1)) / len(options))
    total = option_width * len(options) + gap * (len(options) - 1)
    option_x0, option_y, option_height = (WIDTH - total) / 2, 570, 210
    branch_y = 470
    for index in range(len(options)):
        option_center = option_x0 + index * (option_width + gap) + option_width / 2
        add_poly_arrow(svg, [
            (WIDTH / 2, question_y + question_height),
            (WIDTH / 2, branch_y),
            (option_center, branch_y),
            (option_center, option_y - 6),
        ])
    add_card(svg, question_x, question_y, question_width, question_height, question,
             node_id="decision-question")
    for index, option in enumerate(options):
        add_card(svg, option_x0 + index * (option_width + gap), option_y, option_width, option_height,
                 option, node_id=f"decision-option-{index}")
    return svg


def render_swimlane(spec: dict[str, Any], variant: str) -> ET.Element:
    raw_lanes = require_items(spec, "lanes", 2, 4)
    svg = new_canvas(spec, "swimlane", variant)
    x0, y0, total_width, total_height = 70, 155, 1460, 680
    label_width = 220
    lane_height = total_height / len(raw_lanes)

    for lane_index, raw_lane in enumerate(raw_lanes):
        if not isinstance(raw_lane, dict):
            raise SpecError("each swimlane must be an object")
        title = str(raw_lane.get("title") or f"Lane {lane_index + 1}")
        raw_steps = raw_lane.get("steps")
        if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= 5:
            raise SpecError("each swimlane must contain 1-5 steps")
        steps = [normalize_node(value, index, f"lane-{lane_index}") for index, value in enumerate(raw_steps)]
        y = y0 + lane_index * lane_height
        fill = "#FFFFFF" if lane_index % 2 == 0 else "#F2F4F7"
        add(svg, "rect", x=x0, y=y, width=total_width, height=lane_height - 6, rx=14,
            fill=fill, stroke="#D9DCE0", stroke_width=2, data_role="lane")
        header_id = f"lane-header-{lane_index}"
        accent_fill, accent_stroke = PALETTE[ACCENTS[lane_index % len(ACCENTS)]]
        add(svg, "rect", id=header_id, x=x0, y=y, width=label_width, height=lane_height - 6, rx=14,
            fill=accent_fill, stroke=accent_stroke, stroke_width=2, data_role="lane-header")
        add_text_lines(svg, x0 + label_width / 2, y + lane_height / 2 + 8, title, size=24, weight=700,
                       max_units=8, max_lines=2, role="lane-title", parent_id=header_id)

        step_area_x = x0 + label_width + 30
        step_area_width = total_width - label_width - 60
        gap = 24
        card_width = min(230.0, (step_area_width - gap * (len(steps) - 1)) / len(steps))
        total_cards = card_width * len(steps) + gap * (len(steps) - 1)
        card_x0 = step_area_x + (step_area_width - total_cards) / 2
        card_height = min(112, lane_height - 38)
        card_y = y + (lane_height - 6 - card_height) / 2
        for step_index in range(len(steps) - 1):
            start_x = card_x0 + (step_index + 1) * card_width + step_index * gap
            add_arrow(svg, start_x, card_y + card_height / 2, start_x + gap - 5, card_y + card_height / 2)
        for step_index, step in enumerate(steps):
            add_card(svg, card_x0 + step_index * (card_width + gap), card_y, card_width, card_height, step,
                     node_id=f"lane-{lane_index}-step-{step_index}", compact=True)
    return svg


def render_funnel(spec: dict[str, Any], variant: str) -> ET.Element:
    raw_stages = require_items(spec, "stages", 3, 6)
    stages = [normalize_node(value, index, "funnel") for index, value in enumerate(raw_stages)]
    svg = new_canvas(spec, "funnel", variant)
    center_x, y0, total_height = WIDTH / 2, 150, 690
    stage_height = total_height / len(stages)
    max_width, min_width = 1260, 520

    for index, stage in enumerate(stages):
        top_width = max_width - (max_width - min_width) * index / len(stages)
        bottom_width = max_width - (max_width - min_width) * (index + 1) / len(stages)
        y = y0 + index * stage_height
        gap = 7
        points = [
            (center_x - top_width / 2, y + gap),
            (center_x + top_width / 2, y + gap),
            (center_x + bottom_width / 2, y + stage_height - gap),
            (center_x - bottom_width / 2, y + stage_height - gap),
        ]
        node_id = f"funnel-stage-{index}"
        fill, stroke = PALETTE.get(stage.get("accent", "blue"), PALETTE["blue"])
        add(svg, "polygon", id=node_id,
            points=" ".join(f"{number(x)},{number(py)}" for x, py in points),
            fill=fill, stroke=stroke, stroke_width=2, data_role="node")
        add_text_lines(svg, center_x, y + stage_height / 2 - 6, stage["title"], size=25, weight=700,
                       max_units=max(10, bottom_width / 28), max_lines=1, role="node-title", parent_id=node_id)
        if stage.get("body"):
            add_text_lines(svg, center_x, y + stage_height / 2 + 30, stage["body"], size=20, color="#646A73",
                           max_units=max(12, bottom_width / 24), max_lines=1, role="node-body", parent_id=node_id)
    return svg


def render_quadrant(spec: dict[str, Any], variant: str) -> ET.Element:
    raw_quadrants = require_items(spec, "quadrants", 4, 4)
    quadrants = [normalize_node(value, index, "quadrant") for index, value in enumerate(raw_quadrants)]
    svg = new_canvas(spec, "quadrant", variant)
    x0, y0, size, gap = 235, 175, 1130, 14
    half = (size - gap) / 2
    positions = [
        (x0, y0),
        (x0 + half + gap, y0),
        (x0, y0 + half + gap),
        (x0 + half + gap, y0 + half + gap),
    ]
    default_accents = ["red", "orange", "blue", "green"]
    for index, (quadrant, (x, y)) in enumerate(zip(quadrants, positions)):
        accent = quadrant.get("accent") or default_accents[index]
        fill, stroke = PALETTE.get(accent, PALETTE[default_accents[index]])
        cell_id = f"quadrant-{index}"
        add(svg, "rect", id=cell_id, x=x, y=y, width=half, height=half, rx=20,
            fill=fill, stroke=stroke, stroke_width=2, data_role="quadrant-cell")
        add_text_lines(svg, x + half / 2, y + 78, quadrant["title"], size=28, weight=700,
                       max_units=15, max_lines=2, role="quadrant-title", parent_id=cell_id)
        if quadrant.get("body"):
            add_text_lines(svg, x + half / 2, y + 155, quadrant["body"], size=22, color="#42464D",
                           max_units=19, max_lines=4, line_height=31, role="quadrant-body", parent_id=cell_id)

    add(svg, "line", x1=x0 + size / 2, y1=y0 - 30, x2=x0 + size / 2, y2=y0 + size + 30,
        stroke="#646A73", stroke_width=4, data_role="quadrant-axis")
    add(svg, "line", x1=x0 - 30, y1=y0 + size / 2, x2=x0 + size + 30, y2=y0 + size / 2,
        stroke="#646A73", stroke_width=4, data_role="quadrant-axis")
    labels = spec.get("axis_labels") or {}
    add_text_lines(svg, x0 + size / 2, y0 - 55, str(labels.get("top") or "高"), size=21, weight=700,
                   max_units=10, max_lines=1, role="axis-label")
    add_text_lines(svg, x0 + size / 2, y0 + size + 70, str(labels.get("bottom") or "低"), size=21, weight=700,
                   max_units=10, max_lines=1, role="axis-label")
    add_text_lines(svg, x0 - 70, y0 + size / 2 + 7, str(labels.get("left") or "低"), size=21, weight=700,
                   max_units=10, max_lines=1, role="axis-label")
    add_text_lines(svg, x0 + size + 70, y0 + size / 2 + 7, str(labels.get("right") or "高"), size=21, weight=700,
                   max_units=10, max_lines=1, role="axis-label")
    return svg


def render_cause_effect(spec: dict[str, Any], variant: str) -> ET.Element:
    raw_causes = require_items(spec, "causes", 3, 6)
    causes = [normalize_node(value, index, "cause") for index, value in enumerate(raw_causes)]
    for index, raw_cause in enumerate(raw_causes):
        if isinstance(raw_cause, dict) and isinstance(raw_cause.get("items"), list):
            causes[index]["body"] = " / ".join(str(item) for item in raw_cause["items"][:3])
    effect = normalize_node(spec.get("effect") or "最终结果", 0, "effect")
    svg = new_canvas(spec, "cause-effect", variant)
    spine_y, start_x, effect_x = 470, 120, 1230
    add_arrow(svg, start_x, spine_y, effect_x - 18, spine_y, color="#646A73")
    add_card(svg, effect_x, spine_y - 95, 300, 190, effect, node_id="effect-node")

    top_causes = [cause for index, cause in enumerate(causes) if index % 2 == 0]
    bottom_causes = [cause for index, cause in enumerate(causes) if index % 2 == 1]
    for side, side_causes in (("top", top_causes), ("bottom", bottom_causes)):
        if not side_causes:
            continue
        spacing = 900 / max(1, len(side_causes))
        for index, cause in enumerate(side_causes):
            anchor_x = 300 + spacing * index + spacing / 2
            bone_y = 245 if side == "top" else 695
            category_y = 165 if side == "top" else 700
            add(svg, "line", x1=anchor_x, y1=spine_y, x2=anchor_x - 130, y2=bone_y,
                stroke="#8F959E", stroke_width=4, stroke_linecap="round", data_role="fishbone")
            add_card(svg, anchor_x - 260, category_y, 250, 120, cause,
                     node_id=f"cause-{side}-{index}", compact=True)
    return svg


def render(spec: dict[str, Any]) -> tuple[ET.Element, str]:
    diagram_type = str(spec.get("type") or "").strip()
    variant = select_variant(spec)
    if diagram_type == "flow":
        svg = render_flow(spec, variant)
    elif diagram_type == "knowledge-map":
        svg = render_knowledge_map(spec, variant)
    elif diagram_type == "timeline":
        svg = render_timeline(spec, variant)
    elif diagram_type == "matrix":
        svg = render_matrix(spec, variant)
    elif diagram_type == "decision":
        svg = render_decision(spec, variant)
    elif diagram_type == "swimlane":
        svg = render_swimlane(spec, variant)
    elif diagram_type == "funnel":
        svg = render_funnel(spec, variant)
    elif diagram_type == "quadrant":
        svg = render_quadrant(spec, variant)
    elif diagram_type == "cause-effect":
        svg = render_cause_effect(spec, variant)
    else:
        raise SpecError(f"Unsupported diagram type: {diagram_type}")
    return finalize_canvas(svg, spec), variant


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="UTF-8 JSON diagram specification")
    parser.add_argument("--output", required=True, help="Output SVG path")
    parser.add_argument("--list-types", action="store_true", help="Print supported types and variants")
    args = parser.parse_args()

    if args.list_types:
        print(json.dumps({
            "flow": ["auto", "horizontal", "vertical", "loop"],
            "knowledge-map": ["auto", "radial", "layered"],
            "timeline": ["auto", "linear", "alternating"],
            "matrix": ["auto", "comparison"],
            "decision": ["auto", "branch"],
            "swimlane": ["auto", "lanes"],
            "funnel": ["auto", "descending"],
            "quadrant": ["auto", "2x2"],
            "cause-effect": ["auto", "fishbone"],
        }, ensure_ascii=False, indent=2))
        return 0

    input_path = Path(args.input)
    output_path = Path(args.output)
    try:
        spec = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise SpecError("the diagram specification must be a JSON object")
        svg, variant = render(spec)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(ET.tostring(svg, encoding="unicode"), encoding="utf-8", newline="\n")
    except (OSError, json.JSONDecodeError, SpecError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({
        "ok": True,
        "type": spec.get("type"),
        "variant": variant,
        "output": str(output_path.resolve()),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
