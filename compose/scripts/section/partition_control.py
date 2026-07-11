#!/usr/bin/env python3
"""Control for compose Partition (``_partition.json``).

Subcommands:
    write          Persist atoms JSON (AI-produced) after schema validation
    filter-i-star  Print i_star prose for one section home
    validate       Validate existing ``_partition.json``
    status         Print atom counts by home

CLI details: ``python3 partition_control.py --help``

Design SSOT: docs/biz/compose-section-partition-design.md §6.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from fetch_compose_framework import fetch_compose_framework  # noqa: E402
from partition_schema import (  # noqa: E402
    filter_i_star,
    homes_present,
    load_partition,
    partition_path,
    save_partition,
    validate_partition_atoms,
)


def _section_order(project_root: Path, profile_id: str) -> list[str]:
    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=profile_id,
    )
    data = json.loads(raw)
    return [str(key).upper() for key in data.get("section_order") or []]


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def cmd_write(args: argparse.Namespace) -> int:
    revision_dir = args.revision_dir.resolve()
    path = partition_path(revision_dir)
    try:
        if args.atoms_file:
            raw = Path(args.atoms_file).read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()
        atoms = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(f"cannot read atoms JSON: {exc}")

    allowed = None
    if args.profile:
        try:
            allowed = _section_order(args.project_root.resolve(), args.profile.strip())
        except Exception as exc:  # noqa: BLE001 — surface fetch errors
            return _fail(f"section-registry unavailable: {exc}")

    try:
        save_partition(path, atoms, allowed_homes=allowed)
    except ValueError as exc:
        return _fail(str(exc))

    loaded = load_partition(path)
    return _ok(
        {
            "ok": True,
            "command": "write",
            "path": str(path),
            "atoms_total": len(loaded),
            "by_home": homes_present(loaded),
        }
    )


def cmd_filter_i_star(args: argparse.Namespace) -> int:
    path = partition_path(args.revision_dir.resolve())
    try:
        atoms = load_partition(path)
    except ValueError as exc:
        return _fail(str(exc))
    prose = filter_i_star(atoms, args.section)
    # stdout is the i_star body only (for capture into derive); metadata on stderr if empty
    if not prose.strip():
        print(
            f"partition: no atoms for home={args.section.strip().upper()}",
            file=sys.stderr,
        )
    print(prose, end="" if prose.endswith("\n") or not prose else "\n")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = partition_path(args.revision_dir.resolve())
    if not path.is_file():
        return _fail(f"partition file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON: {exc}")

    allowed = None
    if args.profile:
        try:
            allowed = _section_order(args.project_root.resolve(), args.profile.strip())
        except Exception as exc:  # noqa: BLE001
            return _fail(f"section-registry unavailable: {exc}")

    errors = validate_partition_atoms(data, allowed_homes=allowed)
    if errors:
        return _fail("; ".join(errors))
    atoms = load_partition(path)
    return _ok(
        {
            "ok": True,
            "command": "validate",
            "path": str(path),
            "atoms_total": len(atoms),
            "by_home": homes_present(atoms),
        }
    )


def cmd_status(args: argparse.Namespace) -> int:
    path = partition_path(args.revision_dir.resolve())
    if not path.is_file():
        return _ok(
            {
                "ok": True,
                "command": "status",
                "exists": False,
                "path": str(path),
            }
        )
    try:
        atoms = load_partition(path)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(
        {
            "ok": True,
            "command": "status",
            "exists": True,
            "path": str(path),
            "atoms_total": len(atoms),
            "by_home": homes_present(atoms),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    write_p = sub.add_parser("write", help="Write validated _partition.json")
    write_p.add_argument("--revision-dir", type=Path, required=True)
    write_p.add_argument(
        "--atoms-file",
        type=Path,
        help="Path to atoms JSON array (default: stdin)",
    )
    write_p.add_argument("--profile", type=str, default="")
    write_p.add_argument("--project-root", type=Path, default=Path.cwd())
    write_p.set_defaults(func=cmd_write)

    filter_p = sub.add_parser(
        "filter-i-star",
        help="Print i_star prose for one section home",
    )
    filter_p.add_argument("--revision-dir", type=Path, required=True)
    filter_p.add_argument("--section", type=str, required=True)
    filter_p.set_defaults(func=cmd_filter_i_star)

    validate_p = sub.add_parser("validate", help="Validate _partition.json")
    validate_p.add_argument("--revision-dir", type=Path, required=True)
    validate_p.add_argument("--profile", type=str, default="")
    validate_p.add_argument("--project-root", type=Path, default=Path.cwd())
    validate_p.set_defaults(func=cmd_validate)

    status_p = sub.add_parser("status", help="Partition presence and counts")
    status_p.add_argument("--revision-dir", type=Path, required=True)
    status_p.set_defaults(func=cmd_status)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
