#!/usr/bin/env python3
"""Prepare semantic narrative-arc build input.

``context`` returns the complete current build input for an agent-authored
semantic arc: facts, validated Role/Domain instances, and section registry.

This control never authors or persists an arc.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_RUNNER_SCRIPTS = Path(__file__).resolve().parent
_COMPOSE = _RUNNER_SCRIPTS.parents[1]
_SCRIPTS = _COMPOSE / "scripts"
for _path in (_SCRIPTS, _RUNNER_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from execution_state_schema import execution_dir  # noqa: E402
from domain_instance_schema import (  # noqa: E402
    DOMAIN_SCHEME_KEY,
    load_and_validate_domain_instance,
)
from facts_schema import facts_path, load_facts  # noqa: E402
from section_registry_schema import fetch_section_registry, lens_key_sequence  # noqa: E402
from role_instance_schema import (  # noqa: E402
    ROLE_SCHEME_KEY,
    load_and_validate_role_instance,
)
from schema_common import resolve_fetched_instance_path  # noqa: E402
from scope_resolver import resolve_cycle_type  # noqa: E402
from workflow_paths import resolve_revision_runtime_profile  # noqa: E402
from logs.workflow_log import emit_biz  # noqa: E402


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _slice(revision_dir: str) -> Path:
    return execution_dir(Path(revision_dir).resolve())


def _facts(revision_dir: str) -> list[dict[str, Any]]:
    path = facts_path(_slice(revision_dir))
    if not path.is_file():
        raise ValueError(f"facts not found: {path}")
    return load_facts(path)


def _cycle_type(args: argparse.Namespace) -> str:
    return resolve_cycle_type(
        cycle_id=str(args.cycle_id or "").strip() or None,
        cycle_type=str(args.cycle_type or "").strip() or None,
    )


def _registry(
    *,
    project_root: Path,
    profile: str,
    cycle_id: str,
    profile_path: Path | None = None,
) -> tuple[dict[str, Any], set[str]]:
    data = fetch_section_registry(
        project_root,
        profile_id=profile,
        cycle_id=cycle_id or None,
        profile_path=profile_path,
    )
    lenses = {key for key in lens_key_sequence(data) if key}
    if not lenses:
        raise ValueError("section-registry has no allowed lenses")
    return data, lenses


def _scope_instances(
    *,
    cycle_type: str,
    project_root: Path,
    profile: str,
    cycle_id: str,
    profile_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    role_path = resolve_fetched_instance_path(
        ROLE_SCHEME_KEY,
        project_root,
        profile_id=profile,
        cycle_id=cycle_id or None,
        profile_path=profile_path,
    )
    domain_path = resolve_fetched_instance_path(
        DOMAIN_SCHEME_KEY,
        project_root,
        profile_id=profile,
        cycle_id=cycle_id or None,
        profile_path=profile_path,
    )
    return (
        load_and_validate_role_instance(
            cycle_type,
            path=role_path,
            project_root=project_root,
            profile_id=profile,
        ),
        load_and_validate_domain_instance(
            cycle_type,
            path=domain_path,
            project_root=project_root,
            profile_id=profile,
        ),
    )


def cmd_context(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    conv_id = str(getattr(args, "conversation_id", "") or "").strip() or None
    emit_biz(
        component="narrative-arc",
        event="context.start",
        conversation_id=conv_id,
        project_root=root,
        detail={"revision_dir": str(args.revision_dir)},
    )
    try:
        cycle_type = _cycle_type(args)
        cycle_id = str(args.cycle_id or "").strip()
        runtime = resolve_revision_runtime_profile(
            Path(args.revision_dir),
            root,
            cycle_id=cycle_id or None,
        )
        role, domain = _scope_instances(
            cycle_type=cycle_type,
            project_root=root,
            profile=runtime.profile_id,
            cycle_id=cycle_id,
            profile_path=runtime.profile_path,
        )
        registry, lenses = _registry(
            project_root=root,
            profile=runtime.profile_id,
            cycle_id=cycle_id,
            profile_path=runtime.profile_path,
        )
        facts = _facts(args.revision_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        emit_biz(
            component="narrative-arc",
            event="context.error",
            conversation_id=conv_id,
            project_root=root,
            detail={"error": str(exc)},
        )
        return _fail(str(exc))
    emit_biz(
        component="narrative-arc",
        event="context.end",
        conversation_id=conv_id,
        project_root=root,
        detail={"facts_total": len(facts), "cycle_type": cycle_type},
    )
    return _ok(
        {
            "ok": True,
            "command": "context",
            "slice_dir": str(_slice(args.revision_dir)),
            "cycle_type": cycle_type,
            "facts": facts,
            "role": role,
            "domain": domain,
            "section_registry": registry,
            "allowed_lenses": sorted(lenses),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(command: argparse.ArgumentParser) -> None:
        command.add_argument("--revision-dir", required=True)
        command.add_argument("--project-root", required=True)
        command.add_argument(
            "--conversation-id",
            default="",
            help="Conversation id for workflow biz logs (optional)",
        )
        cycle = command.add_mutually_exclusive_group(required=True)
        cycle.add_argument("--cycle-id", default="")
        cycle.add_argument("--cycle-type", default="")

    context = sub.add_parser("context", help="Print complete semantic-build input")
    add_common(context)
    context.set_defaults(func=cmd_context)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
