#!/usr/bin/env python3
"""Validate plan-kernel profile JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2]
_CORE = _SCRIPTS / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from workflow_paths import PROFILES_DIR

_TECH_PLAN_REQUIRED = frozenset(
    {
        "stage_name",
        "shell_dir",
        "shell_paths",
        "cache_subdir",
        "framework_section",
    }
)
_TECH_PLAN_SHELL_PATHS = frozenset(
    {
        "transition_whitelist",
        "hook_guard",
        "corpora_dir",
        "constraints_instance_dir",
    }
)


def _validate_profile(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path.name}: invalid JSON: {exc}"]

    profile_id = data.get("profile_id")
    expected_id = path.stem
    if profile_id != expected_id:
        errors.append(f"{path.name}: profile_id {profile_id!r} != filename {expected_id!r}")

    if data.get("status") == "placeholder_phase2":
        return errors

    if profile_id == "tech-plan":
        for field in _TECH_PLAN_REQUIRED:
            if field not in data:
                errors.append(f"{path.name}: missing required field {field!r}")
        shell_paths = data.get("shell_paths") or {}
        for key in _TECH_PLAN_SHELL_PATHS:
            if key not in shell_paths:
                errors.append(f"{path.name}: missing shell_paths.{key!r}")

    return errors


def validate_all() -> list[str]:
    errors: list[str] = []
    for path in sorted(PROFILES_DIR.glob("*.json")):
        errors.extend(_validate_profile(path))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate plan-kernel profiles.")
    parser.add_argument("--validate", action="store_true", help="Validate all profiles.")
    args = parser.parse_args()
    if not args.validate:
        parser.print_help()
        return 1
    errors = validate_all()
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    print(f"OK: {len(list(PROFILES_DIR.glob('*.json')))} profile(s) valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
