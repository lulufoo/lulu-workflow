#!/usr/bin/env python3
"""CLI: resolve subagent model from platform config for a workflow stage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from subagent_config import resolve_subagent_model  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve subagent model for a workflow stage.")
    parser.add_argument("--project-root", required=True, help="Project root directory.")
    parser.add_argument("--stage", required=True, help="Workflow stage name (e.g. code).")
    parser.add_argument(
        "--platform",
        default=None,
        choices=["cursor", "copilot"],
        help="Platform override (default: auto-detect).",
    )
    args, _ = parser.parse_known_args(argv)

    project_root = Path(args.project_root).resolve()
    model = resolve_subagent_model(project_root, args.stage, args.platform)
    if model:
        print(json.dumps({"model": model}, ensure_ascii=False))
    else:
        print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
