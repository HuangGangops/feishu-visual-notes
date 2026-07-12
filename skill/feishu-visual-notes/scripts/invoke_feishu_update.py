#!/usr/bin/env python3
"""Validate and update one Feishu document revision without silent fallbacks."""

from __future__ import annotations

import argparse
from pathlib import Path

from feishu_common import assert_block, current_revision, print_json, raw_cli, require_cli_and_user, validate_content, working_file
from runtime_support import cli_json
from snapshot_feishu_document import create_snapshot


COMMANDS = {
    "str_replace", "block_delete", "block_insert_after", "block_replace", "block_copy_insert_after",
    "block_move_after", "overwrite", "append",
}
CONTENT_COMMANDS = {"str_replace", "block_insert_after", "block_replace", "overwrite", "append"}
BLOCK_COMMANDS = {"block_delete", "block_insert_after", "block_replace", "block_copy_insert_after", "block_move_after"}
SOURCE_COMMANDS = {"block_copy_insert_after", "block_move_after"}


def ids(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", required=True)
    parser.add_argument("--command", required=True, choices=sorted(COMMANDS))
    parser.add_argument("--expected-revision", required=True, type=int)
    parser.add_argument("--content-file")
    parser.add_argument("--highlight-inventory-file")
    parser.add_argument("--block-id")
    parser.add_argument("--pattern")
    parser.add_argument("--src-block-ids")
    parser.add_argument("--doc-format", choices=("xml", "markdown"), default="xml")
    parser.add_argument("--minimum-whiteboards", type=int, default=0)
    parser.add_argument("--minimum-highlights", type=int, default=0)
    parser.add_argument("--maximum-highlight-ratio", type=float, default=0.30)
    parser.add_argument("--backup-directory", default=".feishu-backups")
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    try:
        if args.command in CONTENT_COMMANDS and not args.content_file:
            raise ValueError(f"{args.command} requires --content-file.")
        if args.command in BLOCK_COMMANDS and not args.block_id:
            raise ValueError(f"{args.command} requires --block-id.")
        if args.command == "str_replace" and not args.pattern:
            raise ValueError("str_replace requires --pattern.")
        if args.command in SOURCE_COMMANDS and not args.src_block_ids:
            raise ValueError(f"{args.command} requires --src-block-ids.")
        content = working_file(args.content_file) if args.content_file else None
        inventory = working_file(args.highlight_inventory_file) if args.highlight_inventory_file else None
        cli = require_cli_and_user()
        if content:
            validate_content(content, inventory, args.doc_format, args.minimum_whiteboards, args.minimum_highlights, args.maximum_highlight_ratio)
        revision = current_revision(cli, args.doc)
        if revision != args.expected_revision:
            raise RuntimeError(f"Revision conflict before dry-run: expected {args.expected_revision}, found {revision}.")
        for block in ids(args.block_id) + ids(args.src_block_ids):
            assert_block(cli, args.doc, block, revision)
        arguments = [
            "docs", "+update", "--doc", args.doc, "--command", args.command,
            "--doc-format", args.doc_format, "--revision-id", str(args.expected_revision), "--as", "user", "--json",
        ]
        if args.content_file:
            arguments.extend(("--content", "@" + Path(args.content_file).as_posix()))
        if args.block_id:
            arguments.extend(("--block-id", args.block_id))
        if args.pattern:
            arguments.extend(("--pattern", args.pattern))
        if args.src_block_ids:
            arguments.extend(("--src-block-ids", args.src_block_ids))
        dry_run = raw_cli(cli, [*arguments, "--dry-run"])
        if not args.commit:
            print_json({"ok": True, "mode": "dry-run", "identity": "user", "document": args.doc, "revision": revision, "command": args.command, "dry_run": dry_run})
            return 0
        revision_after = current_revision(cli, args.doc)
        if revision_after != args.expected_revision:
            raise RuntimeError(f"Revision conflict after dry-run: expected {args.expected_revision}, found {revision_after}.")
        snapshot = create_snapshot(cli, args.doc, args.expected_revision, args.backup_directory)
        result = cli_json(cli, arguments, timeout=180)
        if not result.get("ok") or result.get("identity") != "user" or result.get("data", {}).get("result") not in {"success", None}:
            raise RuntimeError("The update did not complete successfully.")
        print_json({"ok": True, "mode": "committed", "identity": "user", "backup": snapshot, "result": result})
        return 0
    except Exception as exc:
        print_json({"ok": False, "errors": [str(exc)]})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
