#!/usr/bin/env python3
"""Control for archive-5.0 ``_narrative-arc.json``.

Subcommands:
    validate   Validate arc file (optional --require-write-ready)
    write      Persist arc JSON from --file or stdin
    show       Print normalized arc JSON

CLI: ``python3 narrative_arc_control.py --help``

Process how: docs/domain/archive/compose/archive-5.0/compose-narrative-arc-lens-v2-landing-design.md
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

from discussion_pointer_schema import active_slice_dir  # noqa: E402
from facts_schema import facts_path, load_facts  # noqa: E402
from fetch_compose_framework import fetch_compose_framework  # noqa: E402
from narrative_arc_schema import (  # noqa: E402
    is_write_ready,
    load_narrative_arc,
    narrative_arc_path,
    save_narrative_arc,
    validate_narrative_arc,
)


def _allowed_lenses(project_root: Path, profile_id: str) -> set[str]:
    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=profile_id,
    )
    data = json.loads(raw)
    sections = data.get("sections") or {}
    if isinstance(sections, dict) and sections:
        return {str(k).strip().upper() for k in sections}
    # Transition: registries that still only expose section_order
    order = data.get("section_order") or []
    return {str(k).strip().upper() for k in order if str(k).strip()}


def _load_facts(revision_dir: Path) -> list[dict[str, Any]]:
    path = facts_path(active_slice_dir(Path(revision_dir).resolve()))
    if not path.is_file():
        return []
    return load_facts(path)


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def cmd_validate(args: argparse.Namespace) -> int:
    revision = Path(args.revision_dir).resolve()
    slice_dir = active_slice_dir(revision)
    path = narrative_arc_path(slice_dir)
    if not path.is_file():
        return _fail(f"narrative arc not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON: {exc}")

    facts = _load_facts(revision) if not args.skip_facts else None
    lenses = None
    if args.project_root and args.profile:
        lenses = _allowed_lenses(Path(args.project_root), args.profile)

    errors = validate_narrative_arc(
        data, facts=facts, allowed_lenses=lenses,
    )
    if errors:
        return _fail("; ".join(errors))
    if args.require_write_ready and not is_write_ready(data):
        return _fail("status is not write_ready")
    return _ok(
        {
            "ok": True,
            "path": str(path),
            "status": str(data.get("status", "")).strip(),
            "write_ready": is_write_ready(data),
        }
    )


def cmd_write(args: argparse.Namespace) -> int:
    revision = Path(args.revision_dir).resolve()
    slice_dir = active_slice_dir(revision)
    path = narrative_arc_path(slice_dir)
    if args.file:
        raw_text = Path(args.file).read_text(encoding="utf-8")
    else:
        raw_text = sys.stdin.read()
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON: {exc}")

    facts = _load_facts(revision) if not args.skip_facts else None
    lenses = None
    if args.project_root and args.profile:
        lenses = _allowed_lenses(Path(args.project_root), args.profile)
    try:
        save_narrative_arc(
            path, data, facts=facts, allowed_lenses=lenses,
        )
    except ValueError as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "path": str(path), "status": data.get("status")})


def cmd_show(args: argparse.Namespace) -> int:
    revision = Path(args.revision_dir).resolve()
    slice_dir = active_slice_dir(revision)
    path = narrative_arc_path(slice_dir)
    try:
        data = load_narrative_arc(path)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(data)


def cmd_list_chapters(args: argparse.Namespace) -> int:
    """Emit write units: leaf chapters in document order (requires write_ready)."""
    revision = Path(args.revision_dir).resolve()
    slice_dir = active_slice_dir(revision)
    path = narrative_arc_path(slice_dir)
    facts = _load_facts(revision) if not args.skip_facts else None
    lenses = None
    if args.project_root and args.profile:
        lenses = _allowed_lenses(Path(args.project_root), args.profile)
    try:
        data = load_narrative_arc(path, facts=facts, allowed_lenses=lenses)
    except ValueError as exc:
        return _fail(str(exc))
    if not is_write_ready(data):
        return _fail("list-chapters requires status=write_ready")
    units: list[dict[str, Any]] = []
    for leaf in data.get("leaves") or []:
        leaf_id = str(leaf.get("id", "")).strip()
        leaf_title = str(leaf.get("title", "")).strip()
        for index, chapter in enumerate(leaf.get("chapters") or []):
            lens = str(chapter.get("lens", "")).strip().upper()
            cid = f"{leaf_id}-{lens}" if leaf_id and lens else f"{leaf_id}-C{index}"
            units.append(
                {
                    "chapter_id": cid,
                    "leaf_id": leaf_id,
                    "leaf_title": leaf_title,
                    "lens": lens,
                    "fact_ids": list(chapter.get("fact_ids") or []),
                    "display_title": f"{leaf_title} · {lens}".strip(" ·"),
                }
            )
    return _ok({"ok": True, "chapter_ids": [u["chapter_id"] for u in units], "chapters": units})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_rev(p: argparse.ArgumentParser) -> None:
        p.add_argument("--revision-dir", required=True)
        p.add_argument("--project-root", default="")
        p.add_argument("--profile", default="")
        p.add_argument(
            "--skip-facts",
            action="store_true",
            help="Do not cross-check against _facts.json",
        )

    p_val = sub.add_parser("validate", help="Validate _narrative-arc.json")
    add_rev(p_val)
    p_val.add_argument(
        "--require-write-ready",
        action="store_true",
        help="Fail unless status is write_ready",
    )
    p_val.set_defaults(func=cmd_validate)

    p_write = sub.add_parser("write", help="Write arc JSON from --file or stdin")
    add_rev(p_write)
    p_write.add_argument("--file", default="")
    p_write.set_defaults(func=cmd_write)

    p_show = sub.add_parser("show", help="Print normalized arc JSON")
    add_rev(p_show)
    p_show.set_defaults(func=cmd_show)

    p_list = sub.add_parser(
        "list-chapters",
        help="List write-ready sub-topic chapters in order",
    )
    add_rev(p_list)
    p_list.set_defaults(func=cmd_list_chapters)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
