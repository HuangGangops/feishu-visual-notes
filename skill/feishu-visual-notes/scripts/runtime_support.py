#!/usr/bin/env python3
"""Cross-platform command discovery and process helpers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


MIN_PYTHON = (3, 10, 0)
MIN_NODE = (18, 0, 0)
MIN_LARK_CLI = (1, 0, 67)
TESTED_LARK_CLI = "1.0.67"
MIN_WHITEBOARD_CLI = (0, 2, 12)
TESTED_WHITEBOARD_CLI = "0.2.12"


def version_tuple(value: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    return tuple(int(part) for part in match.groups()) if match else None


def command_path(*names: str) -> Path | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    return None


def run(command: Iterable[str | os.PathLike[str]], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    args = [os.fspath(item) for item in command]
    use_shell = False
    if sys.platform == "win32" and args:
        executable = Path(args[0])
        if executable.suffix.lower() == ".js":
            node = command_path("node", "node.exe")
            if not node:
                raise FileNotFoundError("Node.js is required to run this CLI entry point.")
            args.insert(0, str(node))
            executable = node
        if executable.suffix.lower() not in {".cmd", ".bat"} and not executable.suffix:
            command_wrapper = executable.with_suffix(".cmd")
            if command_wrapper.is_file():
                args[0] = str(command_wrapper)
                executable = command_wrapper
        if executable.suffix.lower() in {".cmd", ".bat"}:
            args = subprocess.list2cmdline(args)
            use_shell = True
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("LARKSUITE_CLI_NO_UPDATE_NOTIFIER", "1")
    env.setdefault("LARKSUITE_CLI_NO_SKILLS_NOTIFIER", "1")
    return subprocess.run(
        args,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=timeout,
        env=env,
        shell=use_shell,
        executable=os.environ.get("COMSPEC") if use_shell else None,
    )


def combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip()).strip()


def npm_global_root() -> Path | None:
    npm = command_path("npm", "npm.cmd")
    if not npm:
        return None
    result = run([npm, "root", "-g"])
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).expanduser()


def package_bin_from_root(package_root: Path, package_name: str, executable: str) -> list[Path]:
    package_dir = package_root.joinpath(*package_name.split("/"))
    package_json = package_dir / "package.json"
    candidates: list[Path] = []
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            binary = data.get("bin")
            relative = binary.get(executable) if isinstance(binary, dict) else binary
            if isinstance(relative, str):
                candidates.append((package_dir / relative).resolve())
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    for suffix in ("", ".cmd", ".exe"):
        candidates.append((package_root / ".bin" / f"{executable}{suffix}").resolve())
    return candidates


def npx_cache_roots() -> list[Path]:
    roots = [Path.home() / ".npm" / "_npx"]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        roots.append(Path(local_app_data) / "npm-cache" / "_npx")
    return roots


def discover_node_cli(executable: str, package_name: str) -> list[Path]:
    names = (executable, f"{executable}.cmd", f"{executable}.exe")
    candidates = [path for name in names if (path := command_path(name))]
    global_root = npm_global_root()
    if global_root:
        candidates.extend(package_bin_from_root(global_root, package_name, executable))
    for common in (Path("/opt/homebrew/bin"), Path("/usr/local/bin")):
        candidates.extend(common / name for name in names)
    for root in npx_cache_roots():
        if not root.is_dir():
            continue
        for node_modules in root.glob("*/node_modules"):
            candidates.extend(package_bin_from_root(node_modules, package_name, executable))
        for name in names:
            candidates.extend(root.glob(f"*/node_modules/.bin/{name}"))
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = os.path.normcase(str(resolved))
        if resolved.is_file() and key not in seen:
            seen.add(key)
            unique.append(resolved)
    return unique


def find_lark_cli(minimum: tuple[int, int, int] = MIN_LARK_CLI) -> tuple[Path | None, str, list[str]]:
    failures: list[str] = []
    candidates = discover_node_cli("lark-cli", "@larksuite/cli")
    candidates.sort(key=lambda path: (path.suffix.lower() == ".js", path.stat().st_mtime), reverse=True)
    for candidate in candidates:
        try:
            version_result = run([candidate, "--version"])
        except (OSError, subprocess.TimeoutExpired) as exc:
            failures.append(f"{candidate}: {exc}")
            continue
        output = combined_output(version_result)
        parsed = version_tuple(output)
        if version_result.returncode != 0 or not parsed:
            failures.append(f"{candidate}: version check failed")
            continue
        if parsed < minimum:
            failures.append(f"{candidate}: version {'.'.join(map(str, parsed))} is below {'.'.join(map(str, minimum))}")
            continue
        try:
            help_result = run([candidate, "--help"])
        except (OSError, subprocess.TimeoutExpired) as exc:
            failures.append(f"{candidate}: {exc}")
            continue
        if help_result.returncode != 0 or "Lark/Feishu CLI" not in combined_output(help_result):
            failures.append(f"{candidate}: help smoke test failed")
            continue
        return candidate, ".".join(map(str, parsed)), failures
    return None, "", failures


def find_whiteboard_cli() -> tuple[Path | None, str]:
    candidates = discover_node_cli("whiteboard-cli", "@larksuite/whiteboard-cli")
    candidates.sort(key=lambda path: (path.suffix.lower() == ".js", path.stat().st_mtime), reverse=True)
    for candidate in candidates:
        try:
            result = run([candidate, "-v"])
        except (OSError, subprocess.TimeoutExpired):
            continue
        parsed = version_tuple(combined_output(result))
        if result.returncode != 0 or not parsed or parsed < MIN_WHITEBOARD_CLI:
            continue
        try:
            help_result = run([candidate, "--help"])
        except (OSError, subprocess.TimeoutExpired):
            continue
        if help_result.returncode == 0 and combined_output(help_result):
            return candidate, ".".join(map(str, parsed))
    root = npm_global_root()
    if root:
        package_json = root / "@larksuite" / "whiteboard-cli" / "package.json"
        if package_json.is_file():
            try:
                version = str(json.loads(package_json.read_text(encoding="utf-8")).get("version", ""))
                parsed = version_tuple(version)
                if parsed and parsed >= MIN_WHITEBOARD_CLI:
                    paths = package_bin_from_root(root, "@larksuite/whiteboard-cli", "whiteboard-cli")
                    for path in paths:
                        if not path.is_file():
                            continue
                        try:
                            help_result = run([path, "--help"])
                        except (OSError, subprocess.TimeoutExpired):
                            continue
                        if help_result.returncode == 0 and combined_output(help_result):
                            return path, version
            except (OSError, UnicodeError, json.JSONDecodeError):
                pass
    return None, ""


def cli_json(cli: Path, arguments: list[str], *, timeout: int = 60) -> dict[str, Any]:
    result = run([cli, *arguments], timeout=timeout)
    output = combined_output(result)
    if result.returncode != 0:
        raise RuntimeError(f"lark-cli failed: {output}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"lark-cli returned non-JSON output: {output}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("lark-cli returned an unexpected JSON value")
    return data


def state_directory() -> Path:
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "feishu-visual-notes"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "feishu-visual-notes"
