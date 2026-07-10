#!/usr/bin/env python3
"""Resolve plan-scope role and domain constraints from per-cycle_type instance files.

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
from typing import Optional

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from domain_instance_schema import load_and_validate_domain_instance  # noqa: E402
from schema_common import VALID_CYCLE_TYPES, validate_all_plan_scope_instances  # noqa: E402
from role_instance_schema import (  # noqa: E402
    get_role_fields,
    get_role_prompt,
    load_and_validate_role_instance,
)
from workflow_common import detect_cycle_type  # noqa: E402


class ScopeResolverError(Exception):
    """Raised when scope constraint resolution fails."""


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
        role = get_role_prompt(data)
        role_fields = get_role_fields(data)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise ScopeResolverError(str(exc)) from exc

    return format_constraints_markdown(resolved, role, role_fields)


def resolve_domain_markdown(
    *,
    cycle_id: str | None = None,
    cycle_type: str | None = None,
    domain_instance_path: Path | None = None,
    project_root: Path | None = None,
    profile_id: str | None = None,
) -> str:
    import json

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


def assemble_inductive_fidelity_text(section_json_path: Path) -> str:
    """Mechanical ``decisions[].text`` assembly for one section (I2 / V5).

    Same contract as ``inductive_g3_section_control.view --synthesis off`` for a
    single section — zero LLM synthesis. Used by Initializing I2a.
    """
    data = json.loads(section_json_path.read_text(encoding="utf-8"))
    texts = [
        str(d.get("text", "")).strip()
        for d in (data.get("decisions") or [])
        if isinstance(d, dict)
    ]
    texts = [t for t in texts if t]
    if not texts:
        return ""
    key = str(data.get("key") or section_json_path.stem)
    return f"## {key}\n\n" + "\n\n".join(texts) + "\n"


def resolve_inductive_slice(section: str, inductive_dir: Path | None) -> str | None:
    """Return the abspath of a per-section inductive slice if it exists, else None.

    Prefer ``{inductive_dir}/{section}.json`` (section-SoT). Legacy
    ``{section}.md`` is accepted only if JSON is absent (transition only).

    Used by Initializing: the inductive slice is the **primary material** for
    that section's decisions (fidelity projection of ``decisions[].text``);
    the upstream scope doc is the Audit-time completeness cross-check, not a
    parallel SoT. Empty/absent inductive dir → no slice.
    """
    key = (section or "").strip()
    if inductive_dir is None or not key:
        return None
    root = Path(inductive_dir)
    json_candidate = root / f"{key}.json"
    if json_candidate.is_file():
        return str(json_candidate.resolve())
    md_candidate = root / f"{key}.md"
    if md_candidate.is_file():
        return str(md_candidate.resolve())
    return None


def resolve_inductive_fidelity(
    section: str, inductive_dir: Path | None
) -> str | None:
    """Return mechanical fidelity markdown for a section, or None if no JSON SoT.

    Prefer this over hand-reading JSON in Initializing (I2/I12). Legacy ``.md``
    paths return None here — caller falls back to reading the md file.
    """
    path = resolve_inductive_slice(section, inductive_dir)
    if not path or not path.endswith(".json"):
        return None
    text = assemble_inductive_fidelity_text(Path(path))
    return text if text.strip() else ""


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compose stage profile plan scope role resolver")
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
    parser.add_argument(
        "--profile",
        default="lulu-plan",
        help="Compose profile id (e.g. lulu-plan, lulu-design, …)",
    )
    sub = parser.add_subparsers(dest="command")

    resolve = sub.add_parser("resolve-role", help="Print Plan Scope Constraints markdown")
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

    domain = sub.add_parser("resolve-domain", help="Print Domain Instance markdown")
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

    grounding = sub.add_parser(
        "resolve-inductive",
        help="Print the per-section inductive scope slice path (empty if none)",
    )
    grounding.add_argument("--section", required=True, help="Section key (e.g. ST, IF)")
    grounding.add_argument(
        "--inductive-dir",
        type=Path,
        help="Inductive per-section scope dir (omit/absent → no slice)",
    )
    grounding.add_argument(
        "--project-root",
        default=".",
        help="Project root (reserved)",
    )

    fidelity = sub.add_parser(
        "resolve-inductive-fidelity",
        help="Print mechanical decisions[].text markdown for a section (I2/V5)",
    )
    fidelity.add_argument("--section", required=True, help="Section key (e.g. ST, IF)")
    fidelity.add_argument(
        "--inductive-dir",
        type=Path,
        help="Inductive per-section scope dir (omit/absent → empty)",
    )
    fidelity.add_argument(
        "--project-root",
        default=".",
        help="Project root (reserved)",
    )

    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    profile_id = getattr(args, "profile", "lulu-plan").strip() or "lulu-plan"

    if args.validate:
        errors = validate_all_plan_scope_instances(project_root)
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        return 0

    if args.command == "resolve-inductive":
        inductive_dir = getattr(args, "inductive_dir", None)
        path = resolve_inductive_slice(args.section, inductive_dir)
        if path:
            sys.stdout.write(path)
        return 0

    if args.command == "resolve-inductive-fidelity":
        inductive_dir = getattr(args, "inductive_dir", None)
        text = resolve_inductive_fidelity(args.section, inductive_dir)
        if text is None:
            return 0
        sys.stdout.write(text)
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
