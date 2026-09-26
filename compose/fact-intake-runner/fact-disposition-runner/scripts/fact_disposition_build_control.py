#!/usr/bin/env python3
"""Prepare mechanical context for fact-disposition-runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_COMPOSE = Path(__file__).resolve().parents[3]
_SCRIPTS = _COMPOSE / "scripts"
_INTAKE_EVAL = Path(__file__).resolve().parents[2] / "fact-intake-eval" / "scripts"
_EVAL_SCRIPTS = _COMPOSE.parent / "eval" / "scripts"
for _path in (_SCRIPTS, _SCRIPTS / "_kernel", _SCRIPTS / "templates", _INTAKE_EVAL, _EVAL_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from eval_path import ensure_eval_script_layers  # noqa: E402

ensure_eval_script_layers()
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from execution_state_schema import execution_dir  # noqa: E402
from evaluate_state_schema import load_evaluate_state  # noqa: E402
from fact_intake_eval_runtime_schema import (  # noqa: E402
    evaluate_state_path,
    gate_allows_derive_from_evaluate_state,
)
from compose_template_loader import (  # noqa: E402
    ComposeTemplateLoadError,
    load_compose_template,
)
from section_registry_schema import fetch_section_registry, lens_key_sequence  # noqa: E402
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
    except (OSError, ValueError) as exc:
        return _fail(str(exc))
    slice_dir = execution_dir(Path(args.revision_dir).resolve())
    es = evaluate_state_path(slice_dir)
    legacy = slice_dir / "atomize-eval" / "evaluate-state.md"
    gate = es if es.is_file() else legacy
    if not gate.is_file():
        return _fail(f"intake eval gate missing (expected {es.as_posix()})")
    try:
        data = load_evaluate_state(gate)
    except (OSError, ValueError) as exc:
        return _fail(f"intake eval gate unreadable: {exc}")
    if not gate_allows_derive_from_evaluate_state(data):
        return _fail(
            f"intake eval not done (eval_status={data.get('eval_status')!r})"
        )
    try:
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
    return _ok(
        {
            "ok": True,
            "command": "context",
            "eval_status": data.get("eval_status"),
            "section_order": lens_key_sequence(reg),
            "consume_policy_rule_ids": [
                str(r.get("id", "")).strip()
                for r in rules
                if isinstance(r, dict) and str(r.get("id", "")).strip()
            ],
            "consume_policy_rules": rules,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    context = sub.add_parser(
        "context",
        help="Fetch disposition context; require intake-eval done",
    )
    context.add_argument("--revision-dir", required=True)
    context.add_argument("--project-root", required=True)
    context.add_argument("--cycle-id", default="")
    context.set_defaults(func=cmd_context)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
