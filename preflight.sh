#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec bash "$ROOT/skill/feishu-visual-notes/scripts/preflight.sh" "$@"
