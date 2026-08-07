#!/usr/bin/env python3
"""Prepare and validate semantic narrative-arc build candidates.

``context`` returns the complete current build input for an agent-authored
semantic arc: facts, validated Role/Domain instances, and section registry.
``validate-candidate`` applies the target-specific Formal or collab gates.

This control never authors or persists an arc. Formal persistence belongs to
``narrative_arc_control.py``; human-confirmed collab persistence belongs to
``narrative_arc_collab_control.py``.
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

from discussion_pointer_schema import active_slice_dir  # noqa: E402
from domain_instance_schema import load_and_validate_domain_instance  # noqa: E402
from facts_schema import facts_path, load_facts  # noqa: E402
from fetch_compose_framework import fetch_compose_framework  # noqa: E402
from narrative_arc_collab_schema import (  # noqa: E402
    collab_fact_coverage_errors,
    validate_narrative_arc_collab,
)
from narrative_arc_schema import validate_narrative_arc  # noqa: E402
from role_instance_schema import load_and_validate_role_instance  # noqa: E402
from scope_resolver import resolve_cycle_type  # noqa: E402


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _slice(revision_dir: str) -> Path:
    return active_slice_dir(Path(revision_dir).resolve())


def _facts(revision_dir: str) -> list[dict[str, Any]]:
    path = facts_path(_slice(revision_dir))
    return load_facts(path) if path.is_file() else []


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
) -> tuple[dict[str, Any], set[str]]:
    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=profile,
        cycle_id=cycle_id or None,
    )
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("section-registry must be a JSON object")
    sections = data.get("sections")
    if isinstance(sections, dict) and sections:
        lenses = {str(key).strip().upper() for key in sections if str(key).strip()}
    else:
        lenses = {
            str(key).strip().upper()
            for key in (data.get("section_order") or [])
            if str(key).strip()
        }
    if not lenses:
        raise ValueError("section-registry has no allowed lenses")
    return data, lenses


def _candidate(path: str) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read candidate: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid candidate JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("candidate root must be an object")
    return data


def cmd_context(args: argparse.Namespace) -> int:
    try:
        root = Path(args.project_root).resolve()
        cycle_type = _cycle_type(args)
        role = load_and_validate_role_instance(
            cycle_type,
            project_root=root,
            profile_id=args.profile,
        )
        domain = load_and_validate_domain_instance(
            cycle_type,
            project_root=root,
            profile_id=args.profile,
        )
        registry, lenses = _registry(
            project_root=root,
            profile=args.profile,
            cycle_id=str(args.cycle_id or "").strip(),
        )
        facts = _facts(args.revision_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _fail(str(exc))
    return _ok(
        {
            "ok": True,
            "command": "context",
            "target": args.target,
            "slice_dir": str(_slice(args.revision_dir)),
            "cycle_type": cycle_type,
            "facts": facts,
            "role": role,
            "domain": domain,
            "section_registry": registry,
            "allowed_lenses": sorted(lenses),
        }
    )


def cmd_validate_candidate(args: argparse.Namespace) -> int:
    try:
        candidate = _candidate(args.file)
        facts = _facts(args.revision_dir)
        if args.target == "formal":
            _, lenses = _registry(
                project_root=Path(args.project_root).resolve(),
                profile=args.profile,
                cycle_id=str(args.cycle_id or "").strip(),
            )
            errors = validate_narrative_arc(
                candidate,
                facts=facts,
                allowed_lenses=lenses,
            )
        else:
            errors = validate_narrative_arc_collab(candidate)
            errors.extend(collab_fact_coverage_errors(candidate, facts))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _fail(str(exc))
    if errors:
        return _fail("; ".join(errors))
    return _ok(
        {
            "ok": True,
            "command": "validate-candidate",
            "target": args.target,
            "facts_total": len(facts),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_context_args(command: argparse.ArgumentParser) -> None:
        command.add_argument("--target", required=True, choices=("formal", "collab"))
        command.add_argument("--revision-dir", required=True)
        command.add_argument("--project-root", required=True)
        command.add_argument("--profile", required=True)
        cycle = command.add_mutually_exclusive_group(required=True)
        cycle.add_argument("--cycle-id", default="")
        cycle.add_argument("--cycle-type", default="")

    context = sub.add_parser("context", help="Print complete semantic-build input")
    add_context_args(context)
    context.set_defaults(func=cmd_context)

    validate = sub.add_parser(
        "validate-candidate",
        help="Validate a semantic arc candidate for its target",
    )
    add_context_args(validate)
    validate.add_argument("--file", required=True)
    validate.set_defaults(func=cmd_validate_candidate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
