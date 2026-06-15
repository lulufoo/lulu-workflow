#!/usr/bin/env python3
"""Resolve plan-scope role constraints from plan-scope-roles.json.

CLI:
    python3 plan_scope.py resolve-role --cycle-id <id> --project-root .
    python3 plan_scope.py resolve-role --cycle-type topic --project-root .
    python3 plan_scope.py --validate --path constraints/plan-scope-roles.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from plan_scope_schema import (  # noqa: E402
    default_roles_path,
    default_role_instances_path,
    default_domain_instance_path,
    get_scope_role,
    get_role_instance,
    load_roles,
    load_role_instances,
    validate_roles,
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
    roles_path: Path | None = None,
    role_instances_path: Path | None = None,
) -> str:
    resolved = resolve_cycle_type(cycle_id=cycle_id, cycle_type=cycle_type)
    path = roles_path or default_roles_path()
    if not path.exists():
        raise PlanScopeError(f"plan-scope-roles not found: {path}")
    try:
        data = load_roles(path)
        role = get_scope_role(data, resolved)
    except ValueError as exc:
        raise PlanScopeError(str(exc)) from exc

    role_fields: dict | None = None
    instances_path = role_instances_path or default_role_instances_path()
    if not instances_path.exists():
        raise PlanScopeError(f"role-instances not found: {instances_path}")
    try:
        instances = load_role_instances(instances_path)
        role_fields = get_role_instance(instances, resolved)
    except (ValueError, KeyError) as exc:
        raise PlanScopeError(
            f"failed to load role instance for {resolved!r} from {instances_path}: {exc}"
        ) from exc

    return format_constraints_markdown(resolved, role, role_fields)


def resolve_domain_markdown(
    *,
    domain_instance_path: Path | None = None,
) -> str:
    import json
    path = domain_instance_path or default_domain_instance_path()
    if not path.exists():
        raise PlanScopeError(f"domain instance not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PlanScopeError(f"failed to read domain instance: {exc}") from exc
    lines = [
        "## Domain Instance",
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
    return resolve_cycle_type(cycle_id=cycle_id, cycle_type=cycle_type)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Tech-plan plan scope role resolver")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate plan-scope-roles.json and exit",
    )
    parser.add_argument(
        "--path",
        type=Path,
        help="Path to plan-scope-roles.json (for --validate)",
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
        "--roles-path",
        type=Path,
        help="Override path to plan-scope-roles.json",
    )

    domain = sub.add_parser("resolve-domain", help="Print Domain Instance markdown")
    domain.add_argument(
        "--project-root",
        default=".",
        help="Project root (reserved; domain instance loads from skill package)",
    )
    domain.add_argument(
        "--domain-path",
        type=Path,
        help="Override path to tech-domain-instance.json",
    )

    args = parser.parse_args(argv)

    if args.validate:
        path = args.path or default_roles_path()
        try:
            data = load_roles(path)
            errors = validate_roles(data)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        return 0

    if args.command == "resolve-domain":
        try:
            content = resolve_domain_markdown(
                domain_instance_path=getattr(args, "domain_path", None),
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
            roles_path=args.roles_path,
        )
    except PlanScopeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
