#!/usr/bin/env python3
"""Repository-level portability and release hygiene tests."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skill" / "feishu-visual-notes"
SCRIPTS = SKILL / "scripts"


def run(*arguments: object, cwd: Path = REPO, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [os.fspath(item) for item in arguments], cwd=cwd, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False, env={**os.environ, "PYTHONUTF8": "1", **(extra_env or {})},
    )


class PortabilityTests(unittest.TestCase):
    def test_frontmatter_and_name(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        self.assertIn("name: feishu-visual-notes", frontmatter)
        self.assertIn("description:", frontmatter)
        self.assertNotIn("metadata:", frontmatter)

    def test_no_old_name_or_private_material(self) -> None:
        forbidden = [
            re.compile("course-notes-" + "visualizer", re.I),
            re.compile("jcn7" + "pjsirw7t", re.I),
            re.compile(r"feishu\.cn/(?:docx|wiki)/", re.I),
            re.compile(r"C:[\\/]Users[\\/]Administrator", re.I),
            re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
        ]
        findings = []
        for path in REPO.rglob("*"):
            if not path.is_file() or ".git" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeError:
                continue
            for pattern in forbidden:
                if pattern.search(text):
                    findings.append(f"{path.relative_to(REPO)}: {pattern.pattern}")
        self.assertEqual([], findings)

    def test_python_compile_and_offline_preflight(self) -> None:
        for path in SCRIPTS.glob("*.py"):
            result = run(sys.executable, "-m", "py_compile", path)
            self.assertEqual(0, result.returncode, result.stderr)
        result = run(sys.executable, SCRIPTS / "preflight.py", "--offline", "--json")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])

    def test_first_run_state_and_mcp_capabilities(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feishu-state-") as temp:
            temp_path = Path(temp)
            capabilities = temp_path / "capabilities.json"
            capabilities.write_text(json.dumps({
                "feishu_mcp": {
                    "available": True,
                    "capabilities": ["document-read", "document-write", "editable-whiteboard"],
                }
            }), encoding="utf-8")
            env = {"LOCALAPPDATA": str(temp_path)}
            first = run(
                sys.executable, SCRIPTS / "preflight.py", "--offline", "--json", "--save",
                "--capabilities-file", capabilities, extra_env=env,
            )
            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            first_payload = json.loads(first.stdout)
            self.assertTrue(first_payload["first_run"])
            self.assertEqual("pass", next(item["status"] for item in first_payload["checks"] if item["name"] == "feishu-mcp"))
            second = run(sys.executable, SCRIPTS / "preflight.py", "--offline", "--json", extra_env=env)
            self.assertEqual(0, second.returncode, second.stdout + second.stderr)
            self.assertFalse(json.loads(second.stdout)["first_run"])

    def test_install_backup_and_failed_stage_rollback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feishu visual 笔记 ") as temp:
            root = Path(temp) / "技能 root"
            installer = SCRIPTS / "install.py"
            first = run(sys.executable, installer, "--destination-root", root, "--json")
            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            target = root / "feishu-visual-notes"
            marker = target / "installation-marker.txt"
            marker.write_text("existing", encoding="utf-8")
            repeated = run(sys.executable, installer, "--destination-root", root, "--json")
            self.assertNotEqual(0, repeated.returncode)
            forced = run(sys.executable, installer, "--destination-root", root, "--force", "--json")
            self.assertEqual(0, forced.returncode, forced.stdout + forced.stderr)
            payload = json.loads(forced.stdout)
            self.assertTrue(Path(payload["backup"]).is_dir())

            broken = Path(temp) / "broken-source" / "feishu-visual-notes"
            shutil.copytree(SKILL, broken)
            (broken / "scripts" / "self_test.py").write_text("raise SystemExit(9)\n", encoding="utf-8")
            failed = run(sys.executable, broken / "scripts" / "install.py", "--destination-root", root, "--force", "--json")
            self.assertNotEqual(0, failed.returncode)
            good_test = run(sys.executable, target / "scripts" / "self_test.py")
            self.assertEqual(0, good_test.returncode, good_test.stdout + good_test.stderr)

    def test_release_archives_are_sanitized(self) -> None:
        with tempfile.TemporaryDirectory(prefix="feishu-release-") as temp:
            result = run(sys.executable, REPO / "tools" / "package_release.py", "--output-directory", temp)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(2, len(payload["artifacts"]))
            zip_path = next(Path(item["path"]) for item in payload["artifacts"] if item["path"].endswith(".zip"))
            tar_path = next(Path(item["path"]) for item in payload["artifacts"] if item["path"].endswith(".tar.gz"))
            with zipfile.ZipFile(zip_path) as archive:
                zip_names = archive.namelist()
            with tarfile.open(tar_path) as archive:
                tar_names = archive.getnames()
            for names in (zip_names, tar_names):
                joined = "\n".join(names)
                self.assertNotRegex(joined, r"__pycache__|\.pyc$|\.feishu-backups|CHANGELOG|README")
                self.assertIn("feishu-visual-notes/SKILL.md", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
