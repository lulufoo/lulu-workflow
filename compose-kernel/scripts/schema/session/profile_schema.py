#!/usr/bin/env python3
"""Validate compose-kernel stage profile JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2]
_CORE = _SCRIPTS / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from workflow_paths import KERNEL_SCHEMES, PROFILES_DIR  # noqa: E402

_TECH_PLAN_REQUIRED = frozenset(
    {
        "stage_name",
        "shell_dir",
        "shell_paths",
        "cache_subdir",
        "framework_section",
        "framework_templates",
        "cycle_types",
    }
)
_TECH_PLAN_SHELL_PATHS = frozenset(
    {
        "hook_guard",
        "dimension_defs_dir",
    }
)
_COMPOSE_SCHEME_PATH = KERNEL_SCHEMES / "compose-template-scheme.json"


def _load_scheme() -> dict:
    return json.loads(_COMPOSE_SCHEME_PATH.read_text(encoding="utf-8"))


def _required_scheme_keys() -> frozenset[str]:
    keys: set[str] = set()
    for entry in _load_scheme().get("templates", []):
        if entry.get("required") == "always" and entry.get("key"):
            keys.add(str(entry["key"]))
    return frozenset(keys)


def _allowed_scheme_keys() -> frozenset[str]:
    keys: set[str] = set()
    for entry in _load_scheme().get("templates", []):
        if entry.get("key"):
            keys.add(str(entry["key"]))
    return frozenset(keys)


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
        cycle_types = data.get("cycle_types") or []
        if not isinstance(cycle_types, list) or not cycle_types:
            errors.append(f"{path.name}: cycle_types must be a non-empty list")
        templates = data.get("framework_templates") or {}
        for scheme_key in _required_scheme_keys():
            if scheme_key not in templates:
                errors.append(f"{path.name}: missing framework_templates[{scheme_key!r}]")
        allowed = _allowed_scheme_keys()
        for scheme_key in templates:
            if scheme_key not in allowed:
                errors.append(
                    f"{path.name}: unknown framework_templates key {scheme_key!r}; "
                    f"allowed: {', '.join(sorted(allowed))}",
                )

    return errors


def validate_all() -> list[str]:
    errors: list[str] = []
    for path in sorted(PROFILES_DIR.glob("*.json")):
        errors.extend(_validate_profile(path))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate compose-kernel stage profiles.")
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
