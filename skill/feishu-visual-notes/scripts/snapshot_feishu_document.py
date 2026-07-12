#!/usr/bin/env python3
"""Save the exact Feishu document revision before an in-place update."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from feishu_common import print_json, require_cli_and_user, working_file
from runtime_support import cli_json


def create_snapshot(cli: Path, doc: str, expected_revision: int, output_directory: str) -> dict[str, Any]:
    output = Path(output_directory)
    if output.is_absolute():
        raise ValueError("Backup directory must be relative to the current working directory.")
    cwd = Path.cwd().resolve()
    resolved = (cwd / output).resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError as exc:
        raise ValueError("Backup directory must remain inside the current working directory.") from exc
    result = cli_json(cli, [
        "docs", "+fetch", "--doc", doc, "--scope", "full", "--detail", "full",
        "--doc-format", "xml", "--revision-id", str(expected_revision), "--as", "user", "--json",
    ], timeout=120)
    document = result.get("data", {}).get("document", {})
    if not result.get("ok") or result.get("identity") != "user" or not document.get("document_id"):
        raise RuntimeError("Snapshot fetch did not return a verified user document.")
    if int(document.get("revision_id", -1)) != expected_revision:
        raise RuntimeError(f"Snapshot revision mismatch: expected {expected_revision}, got {document.get('revision_id')}.")
    resolved.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", str(document["document_id"]))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = resolved / f"{safe_id}-r{expected_revision}-{stamp}.json"
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "identity": "user",
        "source": doc,
        "document_id": document["document_id"],
        "revision_id": expected_revision,
        "content_format": "xml",
        "content": document.get("content", ""),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return {"path": str(path), "document_id": document["document_id"], "revision": expected_revision, "bytes": path.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", required=True)
    parser.add_argument("--expected-revision", required=True, type=int)
    parser.add_argument("--output-directory", default=".feishu-backups")
    args = parser.parse_args()
    try:
        result = create_snapshot(require_cli_and_user(), args.doc, args.expected_revision, args.output_directory)
    except Exception as exc:
        print_json({"ok": False, "errors": [str(exc)]})
        return 1
    print_json({"ok": True, **result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
