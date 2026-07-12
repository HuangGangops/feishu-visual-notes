#!/usr/bin/env python3
"""Shared safety checks for cross-platform Feishu document writes."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from runtime_support import cli_json, combined_output, find_lark_cli, run
from validate_visual_source import validate


def working_file(value: str, *, required: bool = True) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise ValueError(f"Path must be relative to the current working directory: {value}")
    cwd = Path.cwd().resolve()
    resolved = (cwd / path).resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError as exc:
        raise ValueError(f"Path must remain inside the current working directory: {value}") from exc
    if required and not resolved.is_file():
        raise FileNotFoundError(f"File does not exist: {value}")
    return resolved


def require_cli_and_user() -> Path:
    cli, _, failures = find_lark_cli()
    if not cli:
        raise RuntimeError("No compatible Lark/Feishu CLI was found. " + "; ".join(failures[-3:]))
    auth = cli_json(cli, ["auth", "status", "--json", "--verify"])
    if not auth.get("verified") or not auth.get("identities", {}).get("user", {}).get("verified"):
        raise RuntimeError("Feishu user identity is not verified. Run the user login flow before writing.")
    return cli


def run_python(arguments: list[str]) -> str:
    result = run([sys.executable, *arguments], timeout=120)
    output = combined_output(result)
    if result.returncode != 0:
        raise RuntimeError(output)
    return output


def validate_content(
    content: Path,
    inventory: Path | None,
    doc_format: str,
    minimum_whiteboards: int,
    minimum_highlights: int,
    maximum_highlight_ratio: float,
) -> None:
    if doc_format != "xml":
        return
    result = validate(content, minimum_whiteboards, minimum_highlights, maximum_highlight_ratio)
    if not result["ok"]:
        raise RuntimeError("Visual source validation failed: " + " | ".join(result["errors"]))
    text = content.read_text(encoding="utf-8")
    has_highlights = bool(re.search(r'<span\s+[^>]*background-color=', text, re.I))
    if has_highlights and not inventory:
        raise RuntimeError("Highlighted XML requires a highlight inventory.")
    script_root = Path(__file__).resolve().parent
    if inventory:
        run_python([str(script_root / "audit_highlight_coverage.py"), "--content", str(content), "--inventory", str(inventory), "--strict"])
    if re.search(r"<svg\b", text, re.I):
        run_python([str(script_root / "validate_svg_layout.py"), "--input", str(content), "--strict"])
    for match in re.finditer(r'path=["\']@([^"\']+\.svg)["\']', text, re.I):
        svg = working_file(match.group(1))
        run_python([str(script_root / "validate_svg_layout.py"), "--input", str(svg), "--strict"])


def current_revision(cli: Path, doc: str) -> int:
    result = cli_json(cli, [
        "docs", "+fetch", "--doc", doc, "--scope", "outline", "--detail", "full", "--as", "user", "--json",
    ])
    if not result.get("ok") or result.get("identity") != "user":
        raise RuntimeError("The document could not be fetched with user identity.")
    return int(result["data"]["document"]["revision_id"])


def assert_block(cli: Path, doc: str, block_id: str, revision: int) -> None:
    if not block_id or block_id == "-1":
        return
    result = cli_json(cli, [
        "docs", "+fetch", "--doc", doc, "--scope", "range",
        "--start-block-id", block_id, "--end-block-id", block_id,
        "--detail", "full", "--revision-id", str(revision), "--as", "user", "--json",
    ])
    if not result.get("ok") or result.get("identity") != "user":
        raise RuntimeError(f"Block ID does not exist at revision {revision}: {block_id}")


def raw_cli(cli: Path, arguments: list[str]) -> str:
    result = run([cli, *arguments], timeout=120)
    output = combined_output(result)
    if result.returncode != 0:
        raise RuntimeError(f"lark-cli failed: {output}")
    return output


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
