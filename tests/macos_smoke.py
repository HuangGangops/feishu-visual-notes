#!/usr/bin/env python3
"""Run macOS-specific integration checks on a real GitHub-hosted runner."""

from __future__ import annotations

import argparse
import json
import locale
import os
import platform
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skill" / "feishu-visual-notes"


def run(*arguments: object, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-arch", choices=("arm64", "x86_64"), required=True)
    args = parser.parse_args()

    if sys.platform != "darwin":
        raise RuntimeError(f"This smoke test requires macOS, detected {sys.platform}.")
    actual_arch = platform.machine().lower()
    if actual_arch != args.expected_arch:
        raise RuntimeError(f"Expected {args.expected_arch}, detected {actual_arch}.")
    if "utf" not in locale.getpreferredencoding(False).lower():
        raise RuntimeError(f"UTF-8 locale is required, detected {locale.getpreferredencoding(False)}.")

    preflight = run(sys.executable, SKILL / "scripts" / "preflight.py", "--json")
    require_success(preflight, "standard preflight")
    payload = json.loads(preflight.stdout)
    checks = {item["name"]: item for item in payload["checks"]}
    for name in ("operating-system", "python", "node", "npm", "npx", "lark-cli", "whiteboard-cli"):
        if checks[name]["status"] != "pass":
            raise RuntimeError(f"{name} did not pass: {checks[name]}")

    with tempfile.TemporaryDirectory(prefix="feishu macOS 测试 ") as temp:
        temp_path = Path(temp)
        dist = temp_path / "dist"
        package = run(sys.executable, REPO / "tools" / "package_release.py", "--output-directory", dist)
        require_success(package, "release packaging")
        package_payload = json.loads(package.stdout)
        tar_path = next(Path(item["path"]) for item in package_payload["artifacts"] if item["path"].endswith(".tar.gz"))

        extracted = temp_path / "解压目录"
        with tarfile.open(tar_path) as archive:
            archive.extractall(extracted)
        extracted_skill = extracted / "feishu-visual-notes"
        for relative in ("scripts/install.sh", "scripts/preflight.sh", "scripts/install.py"):
            mode = (extracted_skill / relative).stat().st_mode
            if not mode & stat.S_IXUSR:
                raise RuntimeError(f"Executable mode missing after tar extraction: {relative}")

        destination = temp_path / "技能 安装目录"
        install = run("bash", REPO / "install.sh", "--destination-root", destination)
        require_success(install, "Bash installation")
        installed = destination / "feishu-visual-notes"
        self_test = run(sys.executable, installed / "scripts" / "self_test.py")
        require_success(self_test, "installed Skill self-test")
        installed_preflight = run("bash", installed / "scripts" / "preflight.sh", "--offline", "--json")
        require_success(installed_preflight, "installed Bash preflight")

    print(json.dumps({
        "ok": True,
        "platform": platform.platform(),
        "machine": actual_arch,
        "python": platform.python_version(),
        "lark_cli": checks["lark-cli"]["detected"],
        "whiteboard_cli": checks["whiteboard-cli"]["detected"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
