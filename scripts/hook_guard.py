#!/usr/bin/env python3
"""Unified preToolUse entry point. Dispatches to all stage hook_guard scripts."""

import importlib.util
import io
import json
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_STAGES = ["code", "work-order", "tech", "product"]


def _load_stage_module(stage: str):
    path = _SKILL_ROOT / stage / "scripts" / "hook_guard.py"
    stage_scripts = str(path.parent)
    sys.path.insert(0, stage_scripts)
    sys.modules.pop("workflow_common", None)
    try:
        spec = importlib.util.spec_from_file_location(f"_{stage}_hook_guard", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        try:
            sys.path.remove(stage_scripts)
        except ValueError:
            pass
        sys.modules.pop("workflow_common", None)
        sys.modules.pop(f"_{stage}_hook_guard", None)


def main() -> int:
    raw = sys.stdin.read().strip()

    for stage in _STAGES:
        stage_path = _SKILL_ROOT / stage / "scripts" / "hook_guard.py"
        if not stage_path.exists():
            continue

        sys.stdin = io.StringIO(raw)
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            mod = _load_stage_module(stage)
            mod.main()
        except SystemExit:
            pass
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue().strip()
        if output:
            try:
                result = json.loads(output)
            except json.JSONDecodeError:
                continue
            if result.get("permission") == "deny":
                print(json.dumps(result))
                return 0

    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
