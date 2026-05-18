#!/usr/bin/env python3
"""Top-level orchestrator: runs each sub-workflow init.py in sequence.

Hook paths and config defaults are owned by each sub-workflow's own
workflow_common.py / init.py — this script only dispatches to them.
"""

import argparse
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SUB_WORKFLOWS = ["product", "tech", "work-order", "code"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize lulu-dev-workflow in a project (all sub-workflows)."
    )
    parser.add_argument("--project-root", required=True, help="Project root directory.")
    args = parser.parse_args()

    for sub in SUB_WORKFLOWS:
        init_py = SKILL_ROOT / sub / "scripts" / "init.py"
        if not init_py.exists():
            print(f"[lulu-dev-workflow init] WARNING: {init_py} not found, skipping.")
            continue
        print(f"\n[lulu-dev-workflow init] Running {sub} init...")
        result = subprocess.run(
            [sys.executable, str(init_py), "--project-root", args.project_root],
            check=False,
        )
        if result.returncode != 0:
            print(f"[lulu-dev-workflow init] ERROR: {sub} init failed (exit {result.returncode}).")
            return result.returncode

    print("\n[lulu-dev-workflow init] All sub-workflows initialized successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
