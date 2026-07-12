#!/usr/bin/env python3
"""Preview or commit a semantic version change for the repository."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path


SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def bump(value: str, part: str) -> str:
    match = SEMVER.fullmatch(value)
    if not match:
        raise ValueError(f"Invalid semantic version: {value}")
    major, minor, patch = (int(item) for item in match.groups())
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bump", required=True, choices=("major", "minor", "patch"))
    parser.add_argument("--change", action="append", required=True)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    version_path = repo / "skill" / "feishu-visual-notes" / "VERSION"
    changelog_path = repo / "CHANGELOG.md"
    current = version_path.read_text(encoding="utf-8").strip()
    next_version = bump(current, args.bump)
    changelog = changelog_path.read_text(encoding="utf-8")
    if f"## [{current}]" not in changelog:
        raise ValueError("The newest changelog version does not match VERSION.")
    changes = [item.strip() for item in args.change if item.strip()]
    if not changes:
        raise ValueError("At least one non-empty change is required.")
    section = f"## [{next_version}] - {args.date}\n\n### Changed\n\n" + "\n".join(f"- {item}" for item in changes) + "\n\n"
    updated = "# Changelog\n\n" + section + changelog.removeprefix("# Changelog\n\n")
    if args.commit:
        version_path.write_text(next_version + "\n", encoding="utf-8", newline="\n")
        changelog_path.write_text(updated, encoding="utf-8", newline="\n")
    print(json.dumps({
        "ok": True, "mode": "commit" if args.commit else "preview",
        "current_version": current, "next_version": next_version, "changes": changes,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
