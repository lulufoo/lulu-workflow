#!/usr/bin/env python3
"""Prepare mechanical context for fact-cut-runner (cut + disposition)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
for _path in (
    _SCRIPTS,
    _SCRIPTS / "_kernel",
    _SCRIPTS / "templates",
    _SCRIPTS / "facts",
    _SCRIPTS / "schema" / "session",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from project_root import apply_project_root_arg  # noqa: E402

from compose_template_loader import (  # noqa: E402
    ComposeTemplateLoadError,
    load_compose_template,
)
from execution_state_schema import execution_dir  # noqa: E402
from facts_schema import facts_path, load_facts  # noqa: E402
from section_registry_schema import fetch_section_registry, lens_key_sequence  # noqa: E402
from workflow_paths import resolve_revision_runtime_profile  # noqa: E402

_LENS_FIELDS = ("heading", "intent", "intent_boundary")


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _project_lens_registry(registry: dict[str, Any]) -> list[dict[str, str]]:
    sections = registry.get("sections") if isinstance(registry, dict) else {}
    if not isinstance(sections, dict):
        sections = {}
    out: list[dict[str, str]] = []
    for key in lens_key_sequence(registry):
        entry = sections.get(key) or {}
        if not isinstance(entry, dict):
            entry = {}
        item = {"lens": key}
        for field in _LENS_FIELDS:
            value = entry.get(field)
            item[field] = value.strip() if isinstance(value, str) else ""
        out.append(item)
    return out


def _load_facts_snapshot(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        return load_facts(path)
    except ValueError:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []


def cmd_context(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    cycle_id = (args.cycle_id or "").strip() or None
    revision = Path(args.revision_dir).resolve()
    try:
        runtime = resolve_revision_runtime_profile(
            revision,
            root,
            cycle_id=cycle_id,
        )
        reg = fetch_section_registry(
            root,
            profile_id=runtime.profile_id,
            cycle_id=cycle_id,
            profile_path=runtime.profile_path,
        )
        role_raw = load_compose_template(
            "role-instance",
            root,
            profile_id=runtime.profile_id,
            cycle_id=cycle_id,
            profile_path=runtime.profile_path,
        )
        role = json.loads(role_raw)
    except (ComposeTemplateLoadError, OSError, ValueError, json.JSONDecodeError) as exc:
        return _fail(str(exc))
    if not isinstance(role, dict):
        return _fail("role-instance must be a JSON object")
    rules = (role.get("consume_policy") or {}).get("rules") or []
    path = facts_path(execution_dir(revision))
    return _ok(
        {
            "ok": True,
            "command": "context",
            "facts_path": str(path),
            "facts": _load_facts_snapshot(path),
            "lens_registry": _project_lens_registry(reg),
            "consume_policy_rules": rules,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    context = sub.add_parser(
        "context",
        help="Fetch cut+disposition context (facts path, lenses, consume_policy)",
    )
    context.add_argument("--revision-dir", required=True)
    context.add_argument("--project-root")
    context.add_argument("--cycle-id", default="")
    context.set_defaults(func=cmd_context)
    args = parser.parse_args(argv)
    apply_project_root_arg(args)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
