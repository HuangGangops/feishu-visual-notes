#!/usr/bin/env python3
"""Check local requirements before Feishu Visual Notes handles user data."""

from __future__ import annotations

import argparse
import json
import os
import platform
import struct
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from runtime_support import (
    MIN_NODE,
    MIN_PYTHON,
    TESTED_LARK_CLI,
    TESTED_WHITEBOARD_CLI,
    cli_json,
    command_path,
    combined_output,
    find_lark_cli,
    find_whiteboard_cli,
    run,
    state_directory,
    version_tuple,
)


@dataclass
class Check:
    name: str
    status: str
    detected: str = ""
    required: str = ""
    detail: str = ""
    fix_windows: str = ""
    fix_macos: str = ""


def load_capabilities(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Capabilities file must contain a JSON object.")
    return data


def check_command(name: str, commands: tuple[str, ...], minimum: tuple[int, int, int] | None = None) -> Check:
    executable = command_path(*commands)
    if not executable:
        return Check(name, "fail", required="installed and available on PATH")
    result = run([executable, "--version"])
    output = combined_output(result)
    parsed = version_tuple(output)
    if result.returncode != 0:
        return Check(name, "fail", detected=str(executable), detail="Version command failed.")
    if minimum and (not parsed or parsed < minimum):
        return Check(name, "fail", detected=output, required=".".join(map(str, minimum)))
    return Check(name, "pass", detected=output or str(executable), required=".".join(map(str, minimum or ())))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--interactive", action="store_true", help="Print detailed installation guidance")
    parser.add_argument("--check-feishu", action="store_true", help="Verify Feishu CLI and user authentication")
    parser.add_argument("--offline", action="store_true", help="Check only local note-processing requirements")
    parser.add_argument("--capabilities-file", type=Path, help="Runtime MCP/plugin capability report from the host agent")
    parser.add_argument("--save", action="store_true", help="Save this report as the latest first-run state")
    args = parser.parse_args()

    if args.offline and args.check_feishu:
        parser.error("--offline and --check-feishu cannot be used together")

    skill_root = Path(__file__).resolve().parent.parent
    state_path = state_directory() / "preflight-state.json"
    first_run = not state_path.exists()
    machine = platform.machine() or os.environ.get("PROCESSOR_ARCHITECTURE") or f"{struct.calcsize('P') * 8}-bit"
    checks: list[Check] = []
    checks.append(Check(
        "operating-system",
        "pass" if sys.platform in {"win32", "darwin"} else "warn",
        detected=f"{platform.system()} {machine}",
        required="Windows 10/11 or macOS Intel/Apple Silicon",
        detail="Linux is not part of the supported release matrix." if sys.platform not in {"win32", "darwin"} else "",
    ))
    python_version = platform.python_version()
    checks.append(Check(
        "python",
        "pass" if sys.version_info[:3] >= MIN_PYTHON else "fail",
        detected=python_version,
        required=".".join(map(str, MIN_PYTHON)) + "+",
        fix_windows="Install Python 3.10+ from python.org and enable Add Python to PATH.",
        fix_macos="brew install python@3.11",
    ))

    required_files = [
        "SKILL.md", "VERSION", "agents/openai.yaml", "references/diagram-spec.md",
        "references/workflow-spec.md", "scripts/self_test.py", "scripts/build_feishu_diagram.py",
    ]
    missing = [item for item in required_files if not (skill_root / item).is_file()]
    checks.append(Check("skill-files", "fail" if missing else "pass", detail=", ".join(missing)))
    try:
        with tempfile.TemporaryDirectory(prefix="feishu-visual-notes-") as temp:
            test_path = Path(temp) / "中文 utf8.txt"
            test_path.write_text("飞书视觉笔记", encoding="utf-8")
            utf8_ok = test_path.read_text(encoding="utf-8") == "飞书视觉笔记"
    except OSError as exc:
        utf8_ok = False
        temp_detail = str(exc)
    else:
        temp_detail = "UTF-8 read/write succeeded."
    checks.append(Check("utf8-temp", "pass" if utf8_ok else "fail", detail=temp_detail))

    capabilities = load_capabilities(args.capabilities_file)
    feishu_mcp = capabilities.get("feishu_mcp") if isinstance(capabilities, dict) else None
    if isinstance(feishu_mcp, dict) and feishu_mcp.get("available"):
        offered = set(feishu_mcp.get("capabilities", []))
        required = {"document-read", "document-write", "editable-whiteboard"}
        complete = required.issubset(offered)
        checks.append(Check(
            "feishu-mcp",
            "pass" if complete else "warn",
            detected=", ".join(sorted(offered)),
            required=", ".join(sorted(required)),
            detail="MCP is optional and is used only when all required capabilities are verified before work begins.",
        ))
    else:
        checks.append(Check(
            "feishu-mcp",
            "warn",
            detected="not reported",
            detail="The host agent must scan installed MCP/connectors and provide a capabilities file. The tested CLI backend remains available.",
        ))

    if not args.offline:
        checks.append(check_command("node", ("node", "node.exe"), MIN_NODE))
        npm_check = check_command("npm", ("npm", "npm.cmd"))
        npm_check.fix_windows = "Install Node.js LTS from nodejs.org."
        npm_check.fix_macos = "brew install node"
        checks.append(npm_check)
        checks.append(check_command("npx", ("npx", "npx.cmd")))

        lark_cli, lark_version, failures = find_lark_cli()
        if lark_cli:
            checks.append(Check("lark-cli", "pass", detected=f"{lark_version} ({lark_cli})", required=f"{TESTED_LARK_CLI}+"))
        else:
            checks.append(Check(
                "lark-cli", "fail", required=f"{TESTED_LARK_CLI}+", detail="; ".join(failures[-3:]),
                fix_windows=f"npm install -g @larksuite/cli@{TESTED_LARK_CLI}",
                fix_macos=f"npm install -g @larksuite/cli@{TESTED_LARK_CLI}",
            ))

        whiteboard_cli, whiteboard_version = find_whiteboard_cli()
        checks.append(Check(
            "whiteboard-cli",
            "pass" if whiteboard_cli else "fail",
            detected=f"{whiteboard_version} ({whiteboard_cli})" if whiteboard_cli else "not found",
            required=TESTED_WHITEBOARD_CLI,
            fix_windows=f"npm install -g @larksuite/whiteboard-cli@{TESTED_WHITEBOARD_CLI}",
            fix_macos=f"npm install -g @larksuite/whiteboard-cli@{TESTED_WHITEBOARD_CLI}",
        ))

        if args.check_feishu and lark_cli:
            try:
                auth = cli_json(lark_cli, ["auth", "status", "--json", "--verify"])
                verified = bool(auth.get("verified") and auth.get("identities", {}).get("user", {}).get("verified"))
            except RuntimeError as exc:
                verified = False
                auth_detail = str(exc)
            else:
                auth_detail = "User identity verified." if verified else "User identity is not authenticated."
            checks.append(Check(
                "feishu-user-auth", "pass" if verified else "fail", detail=auth_detail,
                fix_windows="Run the user login command shown by: lark-cli auth --help",
                fix_macos="Run the user login command shown by: lark-cli auth --help",
            ))

    failed = [check for check in checks if check.status == "fail"]
    result = {
        "ok": not failed,
        "first_run": first_run,
        "mode": "offline" if args.offline else "feishu" if args.check_feishu else "standard",
        "platform": {"system": platform.system(), "release": platform.release(), "machine": machine},
        "skill_root": str(skill_root),
        "checks": [asdict(check) for check in checks],
        "next_command": f'"{sys.executable}" "{Path(__file__).resolve()}" --check-feishu --interactive',
    }
    if args.save:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["state_path"] = str(state_path)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if first_run:
            print("First run: checking the tools required by Feishu Visual Notes.\n")
        for check in checks:
            detected = f" - {check.detected}" if check.detected else ""
            print(f"[{check.status.upper():4}] {check.name}{detected}")
            if args.interactive and check.status != "pass":
                if check.detail:
                    print(f"       {check.detail}")
                fix = check.fix_windows if sys.platform == "win32" else check.fix_macos
                if fix:
                    print(f"       Fix: {fix}")
        print("\nReady." if result["ok"] else "\nRequired tools are missing. Install them, then run the check again.")
        print(f"Recheck: {result['next_command']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
