#!/usr/bin/env python3
"""Control for unified narrative-arc JSON (archive-25.0).

Subcommands:
    validate   Validate arc at --output-path (optional --require-write-ready)
    write      Persist candidate with digest check + backup
    show       Print normalized arc JSON
    list-chapters

CLI: ``python3 narrative_arc_control.py --help``

Process how: docs/domain/archive/compose/archive-25.0/
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

_RUNNER_SCRIPTS = Path(__file__).resolve().parent
_COMPOSE = _RUNNER_SCRIPTS.parents[1]
_SCRIPTS = _COMPOSE / "scripts"
for _p in (_SCRIPTS, _RUNNER_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_state_lock import canonical_digest  # noqa: E402
from discussion_pointer_schema import active_slice_dir  # noqa: E402
from facts_schema import facts_path, load_facts  # noqa: E402
from fetch_compose_framework import fetch_compose_framework  # noqa: E402
from narrative_arc_schema import (  # noqa: E402
    NARRATIVE_ARC_BASENAME,
    chapter_write_units,
    is_write_ready,
    load_narrative_arc,
    narrative_arc_path,
    save_narrative_arc,
    validate_narrative_arc,
)
from logs.workflow_log import emit_biz  # noqa: E402


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


def _resolve_output(args: argparse.Namespace) -> Path:
    slice_dir = active_slice_dir(Path(args.revision_dir).resolve())
    raw = str(getattr(args, "output_path", "") or "").strip()
    if not raw:
        return narrative_arc_path(slice_dir)
    path = Path(raw)
    if not path.is_absolute():
        path = slice_dir / path
    return path.resolve()


def cmd_validate(args: argparse.Namespace) -> int:
    path = _resolve_output(args)
    if not path.is_file():
        return _fail(f"narrative arc not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON: {exc}")

    revision = Path(args.revision_dir).resolve()
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
    path = _resolve_output(args)
    if not str(args.digest or "").strip():
        return _fail("--digest is required")
    if not str(args.file or "").strip():
        return _fail("--file is required")
    try:
        raw_text = Path(args.file).read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except OSError as exc:
        return _fail(f"cannot read candidate: {exc}")
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON: {exc}")
    if not isinstance(data, dict):
        return _fail("candidate root must be an object")
    if args.digest != canonical_digest(data):
        return _fail("write digest does not match the validated candidate")

    revision = Path(args.revision_dir).resolve()
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

    backup_path: str | None = None
    status = str(data.get("status") or "").strip()
    root = (
        Path(args.project_root).resolve()
        if str(args.project_root or "").strip()
        else Path.cwd().resolve()
    )
    conv_id = str(getattr(args, "conversation_id", "") or "").strip() or None
    emit_biz(
        component="narrative-arc",
        event="write.start",
        conversation_id=conv_id,
        project_root=root,
        detail={"status": status, "path": str(path)},
    )
    try:
        if path.is_file():
            backup = path.with_suffix(path.suffix + f".bak.{int(time.time())}")
            shutil.copy2(path, backup)
            backup_path = str(backup)
        save_narrative_arc(
            path, data, facts=facts, allowed_lenses=lenses,
        )
    except (OSError, ValueError) as exc:
        emit_biz(
            component="narrative-arc",
            event="write.error",
            conversation_id=conv_id,
            project_root=root,
            detail={"error": str(exc), "status": status},
        )
        return _fail(str(exc))
    emit_biz(
        component="narrative-arc",
        event="write.end",
        conversation_id=conv_id,
        project_root=root,
        detail={
            "status": status,
            "write_ready": is_write_ready(data),
            "path": str(path),
        },
    )
    return _ok(
        {
            "ok": True,
            "path": str(path),
            "status": data.get("status"),
            "write_ready": is_write_ready(data),
            "backup": backup_path,
            "default_basename": NARRATIVE_ARC_BASENAME,
        }
    )


def cmd_show(args: argparse.Namespace) -> int:
    path = _resolve_output(args)
    try:
        data = load_narrative_arc(path)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(data)


def cmd_list_chapters(args: argparse.Namespace) -> int:
    path = _resolve_output(args)
    revision = Path(args.revision_dir).resolve()
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
    units = chapter_write_units(data)
    return _ok(
        {
            "ok": True,
            "chapter_ids": [u["chapter_id"] for u in units],
            "chapters": units,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_rev(p: argparse.ArgumentParser) -> None:
        p.add_argument("--revision-dir", required=True)
        p.add_argument("--project-root", default="")
        p.add_argument("--profile", default="")
        p.add_argument(
            "--conversation-id",
            default="",
            help="Conversation id for workflow biz logs (optional)",
        )
        p.add_argument(
            "--output-path",
            default="",
            help=f"Arc path (default: slice/{NARRATIVE_ARC_BASENAME})",
        )
        p.add_argument(
            "--skip-facts",
            action="store_true",
            help="Do not cross-check against _facts.json",
        )

    p_val = sub.add_parser("validate", help="Validate narrative arc at output path")
    add_rev(p_val)
    p_val.add_argument(
        "--require-write-ready",
        action="store_true",
        help="Fail unless status is write_ready",
    )
    p_val.set_defaults(func=cmd_validate)

    p_write = sub.add_parser(
        "write",
        help="Write candidate with digest check and backup",
    )
    add_rev(p_write)
    p_write.add_argument("--file", required=True)
    p_write.add_argument(
        "--digest",
        required=True,
        help="Digest from validate-candidate for the candidate file",
    )
    p_write.add_argument(
        "--require-write-ready",
        action="store_true",
        help="Fail unless candidate status is write_ready",
    )
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
