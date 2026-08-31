#!/usr/bin/env python3
"""Prepare mechanical context for fact-cut-runner (section-registry + role)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
for _path in (_SCRIPTS, _SCRIPTS / "section", _SCRIPTS / "io"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from load_compose_template import (  # noqa: E402
    ComposeTemplateLoadError,
    load_compose_template,
)
from workflow_paths import resolve_revision_runtime_profile  # noqa: E402


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def cmd_context(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    cycle_id = (args.cycle_id or "").strip() or None
    try:
        runtime = resolve_revision_runtime_profile(
            Path(args.revision_dir),
            root,
            cycle_id=cycle_id,
        )
        reg_raw = load_compose_template(
            "section-registry",
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
        reg = json.loads(reg_raw)
        role = json.loads(role_raw)
    except (ComposeTemplateLoadError, OSError, ValueError, json.JSONDecodeError) as exc:
        return _fail(str(exc))
    if not isinstance(reg, dict) or not isinstance(role, dict):
        return _fail("section-registry / role-instance must be JSON objects")
    rules = (role.get("consume_policy") or {}).get("rules") or []
    return _ok(
        {
            "ok": True,
            "command": "context",
            "section_order": [
                str(x).strip().upper()
                for x in (reg.get("section_order") or [])
                if str(x).strip()
            ],
            "consume_policy_rule_ids": [
                str(r.get("id", "")).strip()
                for r in rules
                if isinstance(r, dict) and str(r.get("id", "")).strip()
            ],
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    context = sub.add_parser("context", help="Fetch cut context (registry + role)")
    context.add_argument("--revision-dir", required=True)
    context.add_argument("--project-root", required=True)
    context.add_argument("--cycle-id", default="")
    context.set_defaults(func=cmd_context)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
