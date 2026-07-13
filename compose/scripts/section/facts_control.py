#!/usr/bin/env python3
"""Control for compose Facts (``_facts.json``).

Subcommands:
    write     Persist facts JSON (AI-produced) after schema validation
    filter    Print facts tagged with one lens as a JSON array (addressable)
    validate  Validate existing ``_facts.json``
    status    Print fact counts by lens tag (+ unlensed count)

CLI details: ``python3 facts_control.py --help``

Design SSOT: docs/biz/compose-fact-first-theory/compose-fact-first-display-layer-design.md §3.1, §11 (M1);
optional ``source`` field: compose-fact-first-k1-pd-design.md §3.
Wired into fact-first Init (P0 / Pd / P3).
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
from facts_schema import (  # noqa: E402
    facts_path,
    filter_by_lens,
    lenses_present,
    load_facts,
    save_facts,
    unlensed_fact_ids,
    validate_facts,
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
    path = facts_path(revision_dir)
    try:
        if args.facts_file:
            raw = Path(args.facts_file).read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()
        facts = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(f"cannot read facts JSON: {exc}")

    allowed = None
    if args.profile:
        try:
            allowed = _section_order(args.project_root.resolve(), args.profile.strip())
        except Exception as exc:  # noqa: BLE001 — surface fetch errors
            return _fail(f"section-registry unavailable: {exc}")

    try:
        save_facts(path, facts, allowed_lenses=allowed)
    except ValueError as exc:
        return _fail(str(exc))

    loaded = load_facts(path)
    return _ok(
        {
            "ok": True,
            "command": "write",
            "path": str(path),
            "facts_total": len(loaded),
            "by_lens": lenses_present(loaded),
            "unlensed_total": len(unlensed_fact_ids(loaded)),
        }
    )


def cmd_filter(args: argparse.Namespace) -> int:
    path = facts_path(args.revision_dir.resolve())
    try:
        facts = load_facts(path)
    except ValueError as exc:
        return _fail(str(exc))
    matched = filter_by_lens(facts, args.lens)
    if not matched:
        print(
            f"facts: no facts tagged lens={args.lens.strip().upper()}",
            file=sys.stderr,
        )
    print(json.dumps(matched, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = facts_path(args.revision_dir.resolve())
    if not path.is_file():
        return _fail(f"facts file not found: {path}")
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

    errors = validate_facts(data, allowed_lenses=allowed)
    if errors:
        return _fail("; ".join(errors))
    facts = load_facts(path)
    return _ok(
        {
            "ok": True,
            "command": "validate",
            "path": str(path),
            "facts_total": len(facts),
            "by_lens": lenses_present(facts),
            "unlensed_total": len(unlensed_fact_ids(facts)),
        }
    )


def cmd_status(args: argparse.Namespace) -> int:
    path = facts_path(args.revision_dir.resolve())
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
        facts = load_facts(path)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(
        {
            "ok": True,
            "command": "status",
            "exists": True,
            "path": str(path),
            "facts_total": len(facts),
            "by_lens": lenses_present(facts),
            "unlensed_total": len(unlensed_fact_ids(facts)),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    write_p = sub.add_parser("write", help="Write validated _facts.json")
    write_p.add_argument("--revision-dir", type=Path, required=True)
    write_p.add_argument(
        "--facts-file",
        type=Path,
        help="Path to facts JSON array (default: stdin)",
    )
    write_p.add_argument("--profile", type=str, default="")
    write_p.add_argument("--project-root", type=Path, default=Path.cwd())
    write_p.set_defaults(func=cmd_write)

    filter_p = sub.add_parser(
        "filter",
        help="Print facts tagged with one lens as a JSON array (addressable, not prose)",
    )
    filter_p.add_argument("--revision-dir", type=Path, required=True)
    filter_p.add_argument("--lens", type=str, required=True)
    filter_p.set_defaults(func=cmd_filter)

    validate_p = sub.add_parser("validate", help="Validate _facts.json")
    validate_p.add_argument("--revision-dir", type=Path, required=True)
    validate_p.add_argument("--profile", type=str, default="")
    validate_p.add_argument("--project-root", type=Path, default=Path.cwd())
    validate_p.set_defaults(func=cmd_validate)

    status_p = sub.add_parser("status", help="Facts presence and counts")
    status_p.add_argument("--revision-dir", type=Path, required=True)
    status_p.set_defaults(func=cmd_status)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
