#!/usr/bin/env python3
"""Validate compose stage profile JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2]
_CORE = _SCRIPTS / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from workflow_paths import (  # noqa: E402
    KERNEL_SCHEMES,
    active_compose_stage_ids,
    compose_profile_path,
)

_COMPOSE_PROFILE_REQUIRED = frozenset(
    {
        "stage_name",
        "shell_dir",
        "shell_paths",
        "cache_subdir",
        "framework_section",
        "framework_templates",
        "pipeline",
        "eval",
        "cycle_types",
    }
)
_COMPOSE_SHELL_PATH_KEYS = frozenset(
    {
        "hook_guard",
        "dimension_defs_dir",
    }
)
_COMPOSE_SCHEME_PATH = KERNEL_SCHEMES / "compose-template-scheme.json"
_PIPELINE_REQUIRED = frozenset({"inductive", "freeedit", "code_grounding", "post_writing_options"})
_POST_WRITING_OPTIONS = frozenset({"freeedit", "evaluate"})
_EVAL_REQUIRED = frozenset({"adapter_module", "adapter_class"})


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


def _validate_active_compose_profile(path: Path, data: dict) -> list[str]:
    """Full compose contract for non-placeholder profiles."""
    errors: list[str] = []
    for field in _COMPOSE_PROFILE_REQUIRED:
        if field not in data:
            errors.append(f"{path.name}: missing required field {field!r}")
    shell_paths = data.get("shell_paths") or {}
    for key in _COMPOSE_SHELL_PATH_KEYS:
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
    pipeline = data.get("pipeline")
    if isinstance(pipeline, dict):
        for key in _PIPELINE_REQUIRED:
            if key not in pipeline:
                errors.append(f"{path.name}: missing pipeline.{key}")
        if "display_layer" in pipeline:
            errors.append(
                f"{path.name}: pipeline.display_layer retired "
                "(fact-first Writing is the only path; remove the key)",
            )
        for key in ("inductive", "freeedit", "code_grounding"):
            if key in pipeline and not isinstance(pipeline[key], bool):
                errors.append(f"{path.name}: pipeline.{key} must be a boolean")
        post_writing_options = pipeline.get("post_writing_options")
        if not isinstance(post_writing_options, list) or not post_writing_options:
            errors.append(f"{path.name}: pipeline.post_writing_options must be a non-empty list")
        else:
            for value in post_writing_options:
                if value not in _POST_WRITING_OPTIONS:
                    errors.append(
                        f"{path.name}: unknown pipeline.post_writing_options value {value!r}; "
                        f"allowed: {', '.join(sorted(_POST_WRITING_OPTIONS))}",
                    )
            if "deliver" in post_writing_options:
                errors.append(
                    f"{path.name}: pipeline.post_writing_options must not include "
                    "'deliver' (stage delivery is outer Ready/Deliver)",
                )
    if "start" in data:
        errors.append(
            f"{path.name}: start adapter contract retired; holder preflight owns inputs"
        )
    eval_block = data.get("eval")
    if isinstance(eval_block, dict):
        for key in _EVAL_REQUIRED:
            if key not in eval_block:
                errors.append(f"{path.name}: missing eval.{key}")
            elif not isinstance(eval_block[key], str) or not eval_block[key].strip():
                errors.append(f"{path.name}: eval.{key} must be a non-empty string")
    return errors


def _validate_profile(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path.name}: invalid JSON: {exc}"]

    profile_id = data.get("profile_id")
    expected_id = path.parent.name
    if profile_id != expected_id:
        errors.append(
            f"{path.as_posix()}: profile_id {profile_id!r} != stage dir {expected_id!r}",
        )

    if data.get("status") == "placeholder_phase2":
        return errors

    errors.extend(_validate_active_compose_profile(path, data))
    return errors


def validate_all() -> list[str]:
    errors: list[str] = []
    for stage_id in active_compose_stage_ids():
        path = compose_profile_path(stage_id)
        if not path.is_file():
            errors.append(f"missing compose profile: {path.as_posix()}")
            continue
        errors.extend(_validate_profile(path))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate compose stage profiles.")
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
    stage_ids = active_compose_stage_ids()
    print(f"OK: {len(stage_ids)} compose profile(s) valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
