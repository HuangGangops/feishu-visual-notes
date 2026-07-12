#!/usr/bin/env python3
"""Download a published release package and verify installation end to end."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


REPOSITORY = "HuangGangops/feishu-visual-notes"
SKILL_NAME = "feishu-visual-notes"


def run(*arguments: object, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [os.fspath(item) for item in arguments],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )


def require_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed:\n{result.stdout}\n{result.stderr}")


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "feishu-visual-notes-release-smoke"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_destination(root: Path, member_name: str) -> Path:
    relative = PurePosixPath(member_name)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"Unsafe archive member: {member_name}")
    destination = (root / Path(*relative.parts)).resolve()
    destination.relative_to(root.resolve())
    return destination


def extract(package: Path, destination: Path) -> None:
    if package.suffix == ".zip":
        with zipfile.ZipFile(package) as archive:
            for info in archive.infolist():
                safe_destination(destination, info.filename)
            archive.extractall(destination)
        return
    with tarfile.open(package) as archive:
        for info in archive.getmembers():
            safe_destination(destination, info.name)
            if info.issym() or info.islnk():
                raise RuntimeError(f"Release archive must not contain links: {info.name}")
        archive.extractall(destination)


def check_entry_points(skill: Path) -> None:
    if sys.platform == "win32":
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if not powershell:
            raise RuntimeError("PowerShell is required for the Windows release smoke test.")
        scripts = list(skill.rglob("*.ps1"))
        command = "; ".join(
            f"[void][scriptblock]::Create((Get-Content -LiteralPath '{str(path).replace(chr(39), chr(39) * 2)}' -Raw))"
            for path in scripts
        )
        require_success(run(powershell, "-NoProfile", "-Command", command, cwd=skill), "PowerShell parse")
        return
    for path in skill.rglob("*.sh"):
        if not path.stat().st_mode & stat.S_IXUSR:
            raise RuntimeError(f"Executable mode missing: {path.relative_to(skill)}")
        require_success(run("bash", "-n", path, cwd=skill), f"Bash parse: {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=os.environ.get("RELEASE_TAG"), help="Release tag, for example v1.0.0")
    args = parser.parse_args()
    if not args.tag or not args.tag.startswith("v"):
        raise RuntimeError("A release tag beginning with v is required.")
    version = args.tag[1:]
    suffix = ".zip" if sys.platform == "win32" else ".tar.gz"
    filename = f"{SKILL_NAME}-{version}{suffix}"
    base_url = f"https://github.com/{REPOSITORY}/releases/download/{args.tag}"

    with tempfile.TemporaryDirectory(prefix="feishu release 测试 ") as temp:
        root = Path(temp)
        package = root / filename
        checksum_file = root / f"{filename}.sha256"
        download(f"{base_url}/{filename}", package)
        download(f"{base_url}/{filename}.sha256", checksum_file)
        expected = checksum_file.read_text(encoding="utf-8").split()[0].lower()
        actual = sha256(package)
        if actual != expected:
            raise RuntimeError(f"SHA-256 mismatch: expected {expected}, found {actual}")

        extracted = root / "解压 目录"
        extracted.mkdir()
        extract(package, extracted)
        source_skill = extracted / SKILL_NAME
        check_entry_points(source_skill)

        destination = root / "安装 目录"
        install = run(sys.executable, source_skill / "scripts" / "install.py", "--destination-root", destination, "--json", cwd=source_skill)
        require_success(install, "release installation")
        installed = destination / SKILL_NAME
        require_success(run(sys.executable, installed / "scripts" / "self_test.py", cwd=installed), "installed self-test")
        preflight = run(sys.executable, installed / "scripts" / "preflight.py", "--offline", "--json", cwd=installed)
        require_success(preflight, "installed offline preflight")
        if not json.loads(preflight.stdout)["ok"]:
            raise RuntimeError("Installed offline preflight returned ok=false.")

    print(json.dumps({
        "ok": True,
        "tag": args.tag,
        "package": filename,
        "sha256": actual,
        "platform": sys.platform,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
