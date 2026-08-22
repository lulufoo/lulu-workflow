#!/usr/bin/env python3
"""Materialize lulu-plan runtime compose-profile.json before $START_COMPOSE.

Copies the authoring template into the stage session cache and prints the
absolute path (one line) for ``--profile-path``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose" / "scripts"
if str(_KERNEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_KERNEL_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from workflow_common import CACHE_DIR  # noqa: E402

_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "compose-profile.json"
_INSTANCE_FILENAME = "compose-profile.json"


def materialize_profile(cycle_id: str, project_root: Path) -> Path:
    """Write the session instance and return its absolute path."""
    template = json.loads(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    cache_subdir = str(template.get("cache_subdir", "")).strip()
    if not cache_subdir:
        raise ValueError("authoring compose-profile.json missing cache_subdir")
    out = (
        project_root.resolve()
        / CACHE_DIR
        / cycle_id.strip()
        / cache_subdir
        / _INSTANCE_FILENAME
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return out.resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Write lulu-plan runtime compose-profile.json and print its path"
        ),
    )
    parser.add_argument("--project-root", required=True, help="Project root")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID")
    args = parser.parse_args(argv)
    try:
        path = materialize_profile(
            args.cycle_id.strip(),
            Path(args.project_root).expanduser().resolve(),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    print(path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
