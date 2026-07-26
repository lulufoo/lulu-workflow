#!/usr/bin/env python3
"""Control for archive-5.0 ``_chapter-write-state.json`` (serial chapter Write).

Subcommands:
    sync       Align state order to list-chapters / arc write units
    status     Print next / done_count / status
    begin      Gate + mark chapter in_progress
    complete   Shallow artifact gate + mark done

CLI: ``python3 chapter_write_state_control.py --help``

Process how: docs/domain/archive/compose/archive-5.0/compose-chapter-write-state-design.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from chapter_artifact_paths import chapter_body_path, chapter_derive_path  # noqa: E402
from chapter_write_state_schema import (  # noqa: E402
    chapter_write_state_path,
    compute_top_status,
    load_chapter_write_state,
    next_chapter_id,
    save_chapter_write_state,
)
from discussion_pointer_schema import active_slice_dir  # noqa: E402
from narrative_arc_schema import (  # noqa: E402
    chapter_write_units,
    is_write_ready,
    load_narrative_arc,
    narrative_arc_path,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail_json(payload: dict[str, Any], code: int = 1) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return code


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _slice(revision_dir: Path) -> Path:
    return active_slice_dir(Path(revision_dir).resolve())


def _load_or_empty(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "version": "1",
            "kind": "chapter-write-state",
            "status": "pending",
            "order": [],
            "current": None,
            "by_id": {},
        }
    return load_chapter_write_state(path)


def _check_artifacts(slice_dir: Path, cid: str) -> list[str]:
    errors: list[str] = []
    derive = chapter_derive_path(slice_dir, cid)
    if not derive.is_file():
        errors.append(f"missing derive: {derive.name}")
    else:
        try:
            data = json.loads(derive.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid derive JSON: {exc}")
            data = {}
        if not isinstance(data, dict):
            errors.append("derive must be an object")
        elif not str(data.get("display_title", "")).strip():
            errors.append("empty display_title")
    body = chapter_body_path(slice_dir, cid)
    if not body.is_file():
        errors.append(f"missing body: {body.name}")
    elif not body.read_text(encoding="utf-8").strip():
        errors.append(f"empty body: {body.name}")
    return errors


def cmd_sync(args: argparse.Namespace) -> int:
    slice_dir = _slice(args.revision_dir)
    arc_path = narrative_arc_path(slice_dir)
    if not arc_path.is_file():
        return _fail(f"narrative arc not found: {arc_path}")
    try:
        arc = load_narrative_arc(arc_path)
    except ValueError as exc:
        return _fail(str(exc))
    if not is_write_ready(arc):
        return _fail("sync requires narrative arc status=write_ready")

    units = chapter_write_units(arc)
    path = chapter_write_state_path(slice_dir)
    prev = _load_or_empty(path)
    prev_by = prev.get("by_id") if isinstance(prev.get("by_id"), dict) else {}

    new_order = [u["chapter_id"] for u in units]
    new_by: dict[str, Any] = {}
    for unit in units:
        cid = unit["chapter_id"]
        old = prev_by.get(cid) if isinstance(prev_by.get(cid), dict) else {}
        status = str(old.get("status", "pending")).strip() or "pending"
        if status not in ("pending", "in_progress", "done"):
            status = "pending"
        new_by[cid] = {
            "status": status,
            "leaf_id": unit["leaf_id"],
            "lens": unit["lens"],
            "started_at": old.get("started_at"),
            "completed_at": old.get("completed_at"),
        }

    discarded = [cid for cid in prev.get("order") or [] if cid not in new_by]
    for cid in discarded:
        print(f"warning: discarding chapter write-state entry {cid!r}", file=sys.stderr)

    top = compute_top_status(new_order, new_by)
    current = next_chapter_id(new_order, new_by)
    state = {
        "version": "1",
        "kind": "chapter-write-state",
        "status": top,
        "order": new_order,
        "current": current,
        "by_id": new_by,
        "updated_at": _now(),
    }
    try:
        saved = save_chapter_write_state(path, state)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(
        {
            "ok": True,
            "command": "sync",
            "order": saved["order"],
            "status": saved["status"],
            "discarded": discarded,
            "path": str(path),
        }
    )


def cmd_status(args: argparse.Namespace) -> int:
    slice_dir = _slice(args.revision_dir)
    path = chapter_write_state_path(slice_dir)
    if not path.is_file():
        return _fail(f"chapter write-state not found: {path} (run sync first)")
    try:
        state = load_chapter_write_state(path)
    except ValueError as exc:
        return _fail(str(exc))
    order = state["order"]
    by_id = state["by_id"]
    done = [cid for cid in order if str(by_id[cid].get("status")) == "done"]
    return _ok(
        {
            "ok": True,
            "status": state["status"],
            "current": state.get("current"),
            "next": next_chapter_id(order, by_id),
            "done_count": len(done),
            "total": len(order),
            "done": done,
        }
    )


def cmd_begin(args: argparse.Namespace) -> int:
    slice_dir = _slice(args.revision_dir)
    path = chapter_write_state_path(slice_dir)
    if not path.is_file():
        return _fail(f"chapter write-state not found: {path} (run sync first)")
    try:
        state = load_chapter_write_state(path)
    except ValueError as exc:
        return _fail(str(exc))
    cid = str(args.chapter).strip()
    order = state["order"]
    by_id = state["by_id"]
    if cid not in by_id:
        return _fail_json({"ok": False, "error": "unknown_chapter", "chapter": cid}, 2)
    nxt = next_chapter_id(order, by_id)
    if nxt != cid:
        blocker = nxt
        if cid in order:
            idx = order.index(cid)
            for prev in order[:idx]:
                if str(by_id[prev].get("status")) != "done":
                    blocker = prev
                    break
        return _fail_json(
            {
                "ok": False,
                "error": "gate_failed",
                "blocker": blocker,
                "message": f"previous chapter not done (expected next={nxt!r})",
            },
            3,
        )
    entry = by_id[cid]
    if str(entry.get("status")) == "done":
        return _fail_json(
            {"ok": False, "error": "already_done", "chapter": cid},
            4,
        )
    entry["status"] = "in_progress"
    entry["started_at"] = entry.get("started_at") or _now()
    state["current"] = cid
    state["status"] = compute_top_status(order, by_id)
    state["updated_at"] = _now()
    save_chapter_write_state(path, state)
    return _ok({"ok": True, "command": "begin", "chapter": cid})


def cmd_complete(args: argparse.Namespace) -> int:
    slice_dir = _slice(args.revision_dir)
    path = chapter_write_state_path(slice_dir)
    if not path.is_file():
        return _fail(f"chapter write-state not found: {path} (run sync first)")
    try:
        state = load_chapter_write_state(path)
    except ValueError as exc:
        return _fail(str(exc))
    cid = str(args.chapter).strip()
    order = state["order"]
    by_id = state["by_id"]
    if cid not in by_id:
        return _fail_json({"ok": False, "error": "unknown_chapter", "chapter": cid}, 2)
    idx = order.index(cid) if cid in order else -1
    if idx < 0:
        return _fail_json({"ok": False, "error": "unknown_chapter", "chapter": cid}, 2)
    for prev in order[:idx]:
        if str(by_id[prev].get("status")) != "done":
            return _fail_json(
                {"ok": False, "error": "gate_failed", "blocker": prev},
                3,
            )
    if str(by_id[cid].get("status")) != "in_progress":
        return _fail_json(
            {
                "ok": False,
                "error": "not_in_progress",
                "status": by_id[cid].get("status"),
                "message": "call begin first",
            },
            5,
        )
    errs = _check_artifacts(slice_dir, cid)
    if errs:
        return _fail_json(
            {"ok": False, "error": "artifact_gate_failed", "errors": errs},
            6,
        )
    by_id[cid]["status"] = "done"
    by_id[cid]["completed_at"] = _now()
    nxt = next_chapter_id(order, by_id)
    state["current"] = nxt
    state["status"] = compute_top_status(order, by_id)
    state["updated_at"] = _now()
    save_chapter_write_state(path, state)
    return _ok(
        {
            "ok": True,
            "command": "complete",
            "chapter": cid,
            "next": nxt,
            "status": state["status"],
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_rev(p: argparse.ArgumentParser) -> None:
        p.add_argument("--revision-dir", required=True)

    p_sync = sub.add_parser("sync", help="Align write-state to narrative-arc chapters")
    add_rev(p_sync)
    p_sync.set_defaults(func=cmd_sync)

    p_status = sub.add_parser("status", help="Show write-state progress")
    add_rev(p_status)
    p_status.set_defaults(func=cmd_status)

    p_begin = sub.add_parser("begin", help="Begin writing one chapter")
    add_rev(p_begin)
    p_begin.add_argument("--chapter", required=True)
    p_begin.set_defaults(func=cmd_begin)

    p_complete = sub.add_parser("complete", help="Complete one chapter after artifacts exist")
    add_rev(p_complete)
    p_complete.add_argument("--chapter", required=True)
    p_complete.set_defaults(func=cmd_complete)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
