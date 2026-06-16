#!/usr/bin/env python3
"""Resolve plan-scope role constraints from per-cycle_type role instance files.

CLI:
    python3 plan_scope.py resolve-role --cycle-id <id> --project-root .
    python3 plan_scope.py resolve-role --cycle-type topic --project-root .
    python3 plan_scope.py --validate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from domain_instance_schema import load_and_validate_domain_instance  # noqa: E402
from schema_common import validate_all_plan_scope_instances  # noqa: E402
from role_instance_schema import (  # noqa: E402
    get_role_fields,
    get_role_prompt,
    load_and_validate_role_instance,
)
from workflow_common import detect_cycle_type  # noqa: E402


class PlanScopeError(Exception):
    """Raised when role resolution fails."""


def format_constraints_markdown(cycle_type: str, role: str, role_fields: dict | None = None) -> str:
    import json

    lines = [
        "## Plan Scope Constraints",
        f"cycle_type: {cycle_type}",
        "",
        "### Role",
        role,
        "",
    ]
    if role_fields:
        lines += [
            "### Role Fields",
            "```json",
            json.dumps(role_fields, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    return "\n".join(lines)


def resolve_cycle_type(*, cycle_id: str | None, cycle_type: str | None) -> str:
    if cycle_type is None:
        if not cycle_id:
            raise PlanScopeError("resolve-role requires --cycle-id or --cycle-type")
        cycle_type = detect_cycle_type(cycle_id)
    if cycle_type not in {"topic", "feature"}:
        raise PlanScopeError(
            f"invalid cycle_type: {cycle_type!r} (allowed: feature, topic)",
        )
    return cycle_type


def resolve_role_markdown(
    *,
    cycle_id: str | None = None,
    cycle_type: str | None = None,
    role_instance_path: Path | None = None,
    project_root: Path | None = None,
) -> str:
    resolved = resolve_cycle_type(cycle_id=cycle_id, cycle_type=cycle_type)
    root = Path(project_root).resolve() if project_root is not None else None
    try:
        data = load_and_validate_role_instance(
            resolved,
            path=role_instance_path,
            project_root=root,
        )
        role = get_role_prompt(data)
        role_fields = get_role_fields(data)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise PlanScopeError(str(exc)) from exc

    return format_constraints_markdown(resolved, role, role_fields)


def resolve_domain_markdown(
    *,
    cycle_id: str | None = None,
    cycle_type: str | None = None,
    domain_instance_path: Path | None = None,
    project_root: Path | None = None,
) -> str:
    import json

    resolved = resolve_cycle_type(cycle_id=cycle_id, cycle_type=cycle_type)
    root = Path(project_root).resolve() if project_root is not None else None
    try:
        data = load_and_validate_domain_instance(
            resolved,
            path=domain_instance_path,
            project_root=root,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise PlanScopeError(str(exc)) from exc
    lines = [
        "## Domain Instance",
        f"cycle_type: {resolved}",
        "",
        "```json",
        json.dumps(data, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def resolve_role_summary(
    *,
    cycle_id: str | None = None,
    cycle_type: str | None = None,
    roles_path: Path | None = None,
) -> str:
    del roles_path  # legacy parameter; role instances resolved by cycle_type
    return resolve_cycle_type(cycle_id=cycle_id, cycle_type=cycle_type)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Tech-plan plan scope role resolver")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate role instance JSON files and exit",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root for template cache resolution",
    )
    sub = parser.add_subparsers(dest="command")

    resolve = sub.add_parser("resolve-role", help="Print Plan Scope Constraints markdown")
    resolve.add_argument("--cycle-id", help="Cycle id (infers cycle_type from prefix)")
    resolve.add_argument(
        "--cycle-type",
        choices=["topic", "feature"],
        help="Explicit cycle_type (overrides --cycle-id inference)",
    )
    resolve.add_argument(
        "--project-root",
        default=".",
        help="Project root (reserved; roles load from skill package)",
    )
    resolve.add_argument(
        "--role-instance-path",
        type=Path,
        help="Override path to role instance JSON for resolved cycle_type",
    )

    domain = sub.add_parser("resolve-domain", help="Print Domain Instance markdown")
    domain.add_argument("--cycle-id", help="Cycle id (infers cycle_type from prefix)")
    domain.add_argument(
        "--cycle-type",
        choices=["topic", "feature"],
        help="Explicit cycle_type (overrides --cycle-id inference)",
    )
    domain.add_argument(
        "--project-root",
        default=".",
        help="Project root (reserved; domain instance loads from skill package)",
    )
    domain.add_argument(
        "--domain-instance-path",
        type=Path,
        help="Override path to domain instance JSON for resolved cycle_type",
    )

    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()

    if args.validate:
        errors = validate_all_plan_scope_instances(project_root)
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        return 0

    if args.command == "resolve-domain":
        try:
            content = resolve_domain_markdown(
                cycle_id=getattr(args, "cycle_id", None),
                cycle_type=getattr(args, "cycle_type", None),
                domain_instance_path=getattr(args, "domain_instance_path", None),
                project_root=Path(args.project_root).resolve(),
            )
        except PlanScopeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        sys.stdout.write(content)
        return 0

    if args.command != "resolve-role":
        parser.print_help()
        return 1

    try:
        content = resolve_role_markdown(
            cycle_id=args.cycle_id,
            cycle_type=args.cycle_type,
            role_instance_path=getattr(args, "role_instance_path", None),
            project_root=Path(args.project_root).resolve(),
        )
    except PlanScopeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
