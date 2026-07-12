#!/usr/bin/env python3
"""Install Feishu Visual Notes with staging, validation, backup, and rollback."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


SKILL_NAME = "feishu-visual-notes"
ALLOWED_ROOT_FILES = {"SKILL.md", "VERSION"}
ALLOWED_DIRECTORIES = {"agents", "references", "scripts"}
IGNORED_NAMES = {"__pycache__", ".feishu-backups", ".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def default_destination() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "skills"
    agents = Path.home() / ".agents" / "skills"
    codex = Path.home() / ".codex" / "skills"
    if agents.parent.exists() or not codex.parent.exists():
        return agents
    return codex


def included(relative: Path) -> bool:
    if any(part in IGNORED_NAMES for part in relative.parts) or relative.suffix in IGNORED_SUFFIXES:
        return False
    if len(relative.parts) == 1:
        return relative.name in ALLOWED_ROOT_FILES
    return relative.parts[0] in ALLOWED_DIRECTORIES


def copy_skill(source: Path, target: Path) -> None:
    for item in source.rglob("*"):
        if not item.is_file():
            continue
        relative = item.relative_to(source)
        if not included(relative):
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)


def self_test(skill_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(skill_root / "scripts" / "self_test.py")],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination-root", type=Path, default=default_destination())
    parser.add_argument("--force", action="store_true", help="Replace an existing installation after making a backup")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source = Path(__file__).resolve().parent.parent
    destination_root = args.destination_root.expanduser().resolve()
    target = destination_root / SKILL_NAME
    version = (source / "VERSION").read_text(encoding="utf-8").strip()

    if target.exists() and source == target.resolve():
        result = self_test(source)
        if result.returncode != 0:
            print(result.stdout or result.stderr, file=sys.stderr)
            return 1
        payload = {"ok": True, "mode": "already-installed", "path": str(target), "version": version, "backup": None}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else f"Already installed: {target}")
        return 0

    destination_root.mkdir(parents=True, exist_ok=True)
    stage = destination_root / f".{SKILL_NAME}.installing.{uuid.uuid4().hex}"
    backup_root = destination_root / ".backups"
    backup: Path | None = None
    stage.mkdir(parents=True)
    try:
        copy_skill(source, stage)
        staged_test = self_test(stage)
        if staged_test.returncode != 0:
            raise RuntimeError("Staged self-test failed:\n" + (staged_test.stdout or staged_test.stderr))
        if target.exists():
            if not args.force:
                raise FileExistsError(f"Skill already exists: {target}. Use --force to replace it.")
            backup_root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = backup_root / f"{SKILL_NAME}-{stamp}"
            target.replace(backup)
        stage.replace(target)
        installed_test = self_test(target)
        if installed_test.returncode != 0:
            failed = destination_root / f".{SKILL_NAME}.failed.{uuid.uuid4().hex}"
            target.replace(failed)
            if backup and backup.exists():
                backup.replace(target)
                backup = None
            shutil.rmtree(failed, ignore_errors=True)
            raise RuntimeError("Installed self-test failed; the previous installation was restored.")
    except Exception as exc:
        if not target.exists() and backup and backup.exists():
            backup.replace(target)
            backup = None
        shutil.rmtree(stage, ignore_errors=True)
        print(str(exc), file=sys.stderr)
        return 1

    payload = {"ok": True, "mode": "installed", "path": str(target), "version": version, "backup": str(backup) if backup else None}
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else f"Installed {SKILL_NAME} {version}\nPath: {target}\nBackup: {backup or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
