#!/usr/bin/env python3
"""Build sanitized ZIP and tar.gz Skill archives with SHA-256 files."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


SKILL_NAME = "feishu-visual-notes"
ROOT_FILES = {"SKILL.md", "VERSION"}
ROOT_DIRS = {"agents", "references", "scripts"}
FORBIDDEN_NAMES = {"__pycache__", ".feishu-backups", ".env", ".DS_Store"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".key", ".pem", ".p12"}


def included(relative: Path) -> bool:
    if any(part in FORBIDDEN_NAMES for part in relative.parts) or relative.suffix.lower() in FORBIDDEN_SUFFIXES:
        return False
    if len(relative.parts) == 1:
        return relative.name in ROOT_FILES
    return relative.parts[0] in ROOT_DIRS


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    skill = repo / "skill" / SKILL_NAME
    output = (args.output_directory or repo / "dist").resolve()
    version = (skill / "VERSION").read_text(encoding="utf-8").strip()
    test = subprocess.run(
        [sys.executable, str(skill / "scripts" / "self_test.py")], text=True, encoding="utf-8",
        errors="replace", capture_output=True, check=False, env={**os.environ, "PYTHONUTF8": "1"},
    )
    if test.returncode != 0:
        print(test.stdout or test.stderr, file=sys.stderr)
        return 1

    files = sorted(
        (path for path in skill.rglob("*") if path.is_file() and included(path.relative_to(skill))),
        key=lambda path: path.as_posix(),
    )
    output.mkdir(parents=True, exist_ok=True)
    base = f"{SKILL_NAME}-{version}"
    zip_path = output / f"{base}.zip"
    tar_path = output / f"{base}.tar.gz"
    for target in (zip_path, tar_path):
        if target.exists() and not args.force:
            raise FileExistsError(f"Package already exists: {target}")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = Path(SKILL_NAME) / path.relative_to(skill)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.suffix in {".sh", ".py"} else 0o644) << 16
            archive.writestr(info, path.read_bytes())

    with tarfile.open(tar_path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for path in files:
            relative = Path(SKILL_NAME) / path.relative_to(skill)
            info = archive.gettarinfo(str(path), arcname=relative.as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o755 if path.suffix in {".sh", ".py"} else 0o644
            with path.open("rb") as stream:
                archive.addfile(info, stream)

    artifacts = []
    for path in (zip_path, tar_path):
        checksum = sha256(path)
        checksum_path = path.with_name(path.name + ".sha256")
        checksum_path.write_text(f"{checksum}  {path.name}\n", encoding="utf-8", newline="\n")
        artifacts.append({"path": str(path), "bytes": path.stat().st_size, "sha256": checksum})
    print(json.dumps({"ok": True, "skill": SKILL_NAME, "version": version, "files": len(files), "artifacts": artifacts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
