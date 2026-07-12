#!/usr/bin/env python3
"""Validate and create a Feishu document through the tested user-identity CLI path."""

from __future__ import annotations

import argparse
from pathlib import Path

from feishu_common import print_json, raw_cli, require_cli_and_user, validate_content, working_file
from runtime_support import cli_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-file", required=True)
    parser.add_argument("--highlight-inventory-file")
    parser.add_argument("--doc-format", choices=("xml", "markdown"), default="xml")
    parser.add_argument("--parent-token")
    parser.add_argument("--parent-position")
    parser.add_argument("--minimum-whiteboards", type=int, default=0)
    parser.add_argument("--minimum-highlights", type=int, default=0)
    parser.add_argument("--maximum-highlight-ratio", type=float, default=0.30)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    try:
        if args.parent_token and args.parent_position:
            raise ValueError("--parent-token and --parent-position are mutually exclusive.")
        content = working_file(args.content_file)
        inventory = working_file(args.highlight_inventory_file) if args.highlight_inventory_file else None
        cli = require_cli_and_user()
        validate_content(content, inventory, args.doc_format, args.minimum_whiteboards, args.minimum_highlights, args.maximum_highlight_ratio)
        arguments = [
            "docs", "+create", "--content", "@" + Path(args.content_file).as_posix(),
            "--doc-format", args.doc_format, "--as", "user", "--json",
        ]
        if args.parent_token:
            arguments.extend(("--parent-token", args.parent_token))
        if args.parent_position:
            arguments.extend(("--parent-position", args.parent_position))
        dry_run = raw_cli(cli, [*arguments, "--dry-run"])
        if not args.commit:
            print_json({"ok": True, "mode": "dry-run", "identity": "user", "content_file": args.content_file, "dry_run": dry_run})
            return 0
        require_cli_and_user()
        result = cli_json(cli, arguments, timeout=180)
        document = result.get("data", {}).get("document", {})
        if not result.get("ok") or result.get("identity") != "user" or not document.get("document_id"):
            raise RuntimeError("Document creation did not return a verified user document.")
        outline = cli_json(cli, [
            "docs", "+fetch", "--doc", document["url"], "--scope", "outline", "--detail", "with-ids", "--as", "user", "--json",
        ])
        if not outline.get("ok") or outline.get("identity") != "user":
            raise RuntimeError("Document created, but post-create outline verification failed.")
        print_json({"ok": True, "mode": "committed", "identity": "user", "document": document, "outline": outline.get("data", {}).get("document")})
        return 0
    except Exception as exc:
        print_json({"ok": False, "errors": [str(exc)]})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
