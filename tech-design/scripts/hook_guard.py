#!/usr/bin/env python3
"""Stage guard: only allow writes inside the workflow cache."""

import json
import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[2]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts"
if str(_KERNEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_KERNEL_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from workflow_common import CACHE_DIR, normalize_tool_path  # noqa: E402

STAGE = "tech-design"

_SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))
from workflow_hook_common import deny_cache_boundary  # noqa: E402


def allow() -> dict:
    return {"permission": "allow"}


def main() -> int:
    project_root = Path.cwd()

    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps(allow()))
        return 0

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        print(json.dumps(allow()))
        return 0

    tool_name = str(event.get("tool_name") or event.get("tool") or "")
    if tool_name not in {"Write", "Edit"}:
        print(json.dumps(allow()))
        return 0

    tool_input = event.get("tool_input") or event.get("arguments") or {}
    raw_path = (
        tool_input.get("path")
        or tool_input.get("target_file")
        or tool_input.get("file_path")
        or ""
    )
    if not raw_path:
        print(json.dumps(allow()))
        return 0

    rel = normalize_tool_path(str(raw_path), project_root)
    abs_path = (project_root / rel).resolve()
    workflow_cache = (project_root / CACHE_DIR).resolve()

    try:
        abs_path.relative_to(workflow_cache)
    except ValueError:
        print(json.dumps(deny_cache_boundary(
            stage=STAGE,
            cache_dir=workflow_cache,
            target_path=abs_path,
        )))
        return 0

    print(json.dumps(allow()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
