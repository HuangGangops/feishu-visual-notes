#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if command -v python3 >/dev/null 2>&1; then PYTHON=python3; else PYTHON=python; fi
exec "$PYTHON" "$SCRIPT_DIR/install.py" "$@"
