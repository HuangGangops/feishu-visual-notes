#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python 3.10+ is required. On macOS, run: brew install python@3.11" >&2
  exit 1
fi
exec "$PYTHON" "$SCRIPT_DIR/preflight.py" "$@"
