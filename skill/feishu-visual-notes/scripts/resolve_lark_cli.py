#!/usr/bin/env python3
"""Print the verified cross-platform Lark/Feishu CLI path."""

from __future__ import annotations

import argparse
import sys

from runtime_support import find_lark_cli, version_tuple


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum-version", default="1.0.67")
    args = parser.parse_args()
    minimum = version_tuple(args.minimum_version)
    if not minimum:
        parser.error("--minimum-version must be semantic versioning")
    path, _, failures = find_lark_cli(minimum)
    if not path:
        detail = "; ".join(failures[-5:])
        print(f"No working Lark CLI >= {args.minimum_version} was found. {detail}".strip(), file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
