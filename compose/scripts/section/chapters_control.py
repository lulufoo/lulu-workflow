#!/usr/bin/env python3
"""Control for compose display chapters (``_chapters.json``).

Subcommands:
    write     Persist chapters JSON (AI-produced) after schema validation
    validate  Validate existing ``_chapters.json``
    status    Print chapter/fact counts and op breakdown

CLI details: ``python3 chapters_control.py --help``

Design rationale (source repo, why-only): docs/domain/ssot/compose/mechanism-ssot/compose-display-architecture.md;
process how archive: docs/domain/archive/compose/archive-2.0/compose-fact-first-display-layer-design.md §3.4, §11.2 (M2).
Consumed by fact-first Init (Step 4 / Step 6) via ``display_layer_gates.py``.
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
from chapters_schema import (  # noqa: E402
    chapters_path,
    fact_ids_by_chapter,
    load_chapters,
    save_chapters,
    validate_chapters,
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


def _op_counts(chapters: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chapter in chapters:
        op = chapter.get("op", "")
        counts[op] = counts.get(op, 0) + 1
    return counts


def cmd_write(args: argparse.Namespace) -> int:
    revision_dir = args.revision_dir.resolve()
    path = chapters_path(revision_dir)
    try:
        if args.chapters_file:
            raw = Path(args.chapters_file).read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()
        chapters = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(f"cannot read chapters JSON: {exc}")

    allowed = None
    if args.profile:
        try:
            allowed = _section_order(args.project_root.resolve(), args.profile.strip())
        except Exception as exc:  # noqa: BLE001 — surface fetch errors
            return _fail(f"section-registry unavailable: {exc}")

    try:
        save_chapters(path, chapters, allowed_lenses=allowed)
    except ValueError as exc:
        return _fail(str(exc))

    loaded = load_chapters(path)
    return _ok(
        {
            "ok": True,
            "command": "write",
            "path": str(path),
            "chapters_total": len(loaded),
            "by_op": _op_counts(loaded),
            "facts_placed_total": sum(len(v) for v in fact_ids_by_chapter(loaded).values()),
        }
    )


def cmd_validate(args: argparse.Namespace) -> int:
    path = chapters_path(args.revision_dir.resolve())
    if not path.is_file():
        return _fail(f"chapters file not found: {path}")
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

    errors = validate_chapters(data, allowed_lenses=allowed)
    if errors:
        return _fail("; ".join(errors))
    chapters = load_chapters(path)
    return _ok(
        {
            "ok": True,
            "command": "validate",
            "path": str(path),
            "chapters_total": len(chapters),
            "by_op": _op_counts(chapters),
            "facts_placed_total": sum(len(v) for v in fact_ids_by_chapter(chapters).values()),
        }
    )


def cmd_status(args: argparse.Namespace) -> int:
    path = chapters_path(args.revision_dir.resolve())
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
        chapters = load_chapters(path)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(
        {
            "ok": True,
            "command": "status",
            "exists": True,
            "path": str(path),
            "chapters_total": len(chapters),
            "by_op": _op_counts(chapters),
            "facts_placed_total": sum(len(v) for v in fact_ids_by_chapter(chapters).values()),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    write_p = sub.add_parser("write", help="Write validated _chapters.json")
    write_p.add_argument("--revision-dir", type=Path, required=True)
    write_p.add_argument(
        "--chapters-file",
        type=Path,
        help="Path to chapters JSON array (default: stdin)",
    )
    write_p.add_argument("--profile", type=str, default="")
    write_p.add_argument("--project-root", type=Path, default=Path.cwd())
    write_p.set_defaults(func=cmd_write)

    validate_p = sub.add_parser("validate", help="Validate _chapters.json")
    validate_p.add_argument("--revision-dir", type=Path, required=True)
    validate_p.add_argument("--profile", type=str, default="")
    validate_p.add_argument("--project-root", type=Path, default=Path.cwd())
    validate_p.set_defaults(func=cmd_validate)

    status_p = sub.add_parser("status", help="Chapters presence and counts")
    status_p.add_argument("--revision-dir", type=Path, required=True)
    status_p.set_defaults(func=cmd_status)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
