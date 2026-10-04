#!/usr/bin/env python3
"""Resolve scope role and domain constraints from per-cycle_type instance files.

CLI:
    python3 scope_resolver.py resolve-role --cycle-id <id> --project-root .
    python3 scope_resolver.py resolve-role --cycle-type feature --project-root .
    python3 scope_resolver.py resolve-domain --cycle-id <id> --project-root .
    python3 scope_resolver.py --validate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from project_root import apply_project_root_arg  # noqa: E402

from domain_instance_schema import load_and_validate_domain_instance  # noqa: E402
from schema_common import VALID_CYCLE_TYPES, validate_all_plan_scope_instances  # noqa: E402
from role_instance_schema import load_and_validate_role_instance  # noqa: E402
from workflow_common import detect_cycle_type  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, resolve_profile_id  # noqa: E402


class ScopeResolverError(Exception):
    """Raised when scope constraint resolution fails."""


def format_instance_markdown(
    *,
    cycle_type: str,
    section_heading: str,
    data: dict[str, Any],
) -> str:
    """Render one Scope Constraints section as markdown + JSON."""
    lines = [
        "## Scope Constraints",
        f"cycle_type: {cycle_type}",
        "",
        section_heading,
        "```json",
        json.dumps(data, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def resolve_cycle_type(*, cycle_id: str | None, cycle_type: str | None) -> str:
    if cycle_type is None:
        if not cycle_id:
            raise ScopeResolverError("resolve-role requires --cycle-id or --cycle-type")
        cycle_type = detect_cycle_type(cycle_id)
    if cycle_type not in VALID_CYCLE_TYPES:
        raise ScopeResolverError(
            f"invalid cycle_type: {cycle_type!r} (allowed: {sorted(VALID_CYCLE_TYPES)})",
        )
    return cycle_type


def resolve_role_markdown(
    *,
    cycle_id: str | None = None,
    cycle_type: str | None = None,
    role_instance_path: Path | None = None,
    project_root: Path | None = None,
    profile_id: str | None = None,
) -> str:
    resolved = resolve_cycle_type(cycle_id=cycle_id, cycle_type=cycle_type)
    root = Path(project_root).resolve() if project_root is not None else None
    try:
        data = load_and_validate_role_instance(
            resolved,
            path=role_instance_path,
            project_root=root,
            profile_id=profile_id,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise ScopeResolverError(str(exc)) from exc

    return format_instance_markdown(
        cycle_type=resolved,
        section_heading="### Role Instance",
        data=data,
    )


def resolve_domain_markdown(
    *,
    cycle_id: str | None = None,
    cycle_type: str | None = None,
    domain_instance_path: Path | None = None,
    project_root: Path | None = None,
    profile_id: str | None = None,
) -> str:
    resolved = resolve_cycle_type(cycle_id=cycle_id, cycle_type=cycle_type)
    root = Path(project_root).resolve() if project_root is not None else None
    try:
        data = load_and_validate_domain_instance(
            resolved,
            path=domain_instance_path,
            project_root=root,
            profile_id=profile_id,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise ScopeResolverError(str(exc)) from exc
    return format_instance_markdown(
        cycle_type=resolved,
        section_heading="### Domain Instance",
        data=data,
    )


def resolve_role_summary(
    *,
    cycle_id: str | None = None,
    cycle_type: str | None = None,
    roles_path: Path | None = None,
) -> str:
    del roles_path  # legacy parameter; role instances resolved by cycle_type
    return resolve_cycle_type(cycle_id=cycle_id, cycle_type=cycle_type)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compose stage scope role/domain resolver")
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

    resolve = sub.add_parser(
        "resolve-role",
        help="Print Scope Constraints markdown (Role Instance)",
    )
    resolve.add_argument("--cycle-id", help="Cycle id (infers cycle_type from prefix)")
    resolve.add_argument(
        "--cycle-type",
        choices=sorted(VALID_CYCLE_TYPES),
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

    domain = sub.add_parser(
        "resolve-domain",
        help="Print Scope Constraints markdown (Domain Instance)",
    )
    domain.add_argument("--cycle-id", help="Cycle id (infers cycle_type from prefix)")
    domain.add_argument(
        "--cycle-type",
        choices=sorted(VALID_CYCLE_TYPES),
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
    apply_project_root_arg(args)
    project_root = Path(args.project_root).resolve()
    cycle_id = getattr(args, "cycle_id", None)
    if cycle_id:
        try:
            profile_id = resolve_profile_id(
                project_root=project_root,
                cycle_id=str(cycle_id),
            )
        except (ValueError, FileNotFoundError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    else:
        profile_id = DEFAULT_COMPOSE_PROFILE_ID

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
                profile_id=profile_id,
            )
        except ScopeResolverError as exc:
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
            profile_id=profile_id,
        )
    except ScopeResolverError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
