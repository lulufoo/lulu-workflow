#!/usr/bin/env python3
"""Control for archive-5.0 ``_chapter-write-state.json`` (claim-current serial Write).

Subcommands:
    sync       Align state order to narrative-arc write units
    status     Print next / done_count / status (observe only)
    begin      Claim current chapter (no --chapter); return work ticket
    complete   Artifact gate + mark current done; advance next

CLI: ``python3 chapter_write_state_control.py --help``

Process how:
docs/domain/archive/compose/archive-5.0/compose-chapter-write-claim-current-design.md
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

from chapter_fc_gates import check_chapter_write_artifacts  # noqa: E402
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
    return check_chapter_write_artifacts(slice_dir, cid)


def _in_progress_cid(order: list[str], by_id: dict[str, Any]) -> str | None:
    for cid in order:
        if str((by_id.get(cid) or {}).get("status", "")).strip() == "in_progress":
            return cid
    return None


def _unit_by_id(arc: dict[str, Any], cid: str) -> dict[str, Any] | None:
    for unit in chapter_write_units(arc):
        if unit.get("chapter_id") == cid:
            return unit
    return None


def _load_arc(slice_dir: Path) -> dict[str, Any]:
    return load_narrative_arc(narrative_arc_path(slice_dir))


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
    running = _in_progress_cid(new_order, new_by)
    current = running or next_chapter_id(new_order, new_by)
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
            "running": _in_progress_cid(order, by_id),
            "done_count": len(done),
            "total": len(order),
            "done": done,
        }
    )


def cmd_begin(args: argparse.Namespace) -> int:
    """Claim the sole current chapter (claim-current). No --chapter."""
    if getattr(args, "chapter", None):
        return _fail_json(
            {
                "ok": False,
                "error": "chapter_arg_forbidden",
                "message": (
                    "begin does not accept --chapter; omit it and use the "
                    "returned work ticket (claim-current)"
                ),
            },
            2,
        )

    slice_dir = _slice(args.revision_dir)
    path = chapter_write_state_path(slice_dir)
    if not path.is_file():
        return _fail(f"chapter write-state not found: {path} (run sync first)")
    try:
        state = load_chapter_write_state(path)
        arc = _load_arc(slice_dir)
    except ValueError as exc:
        return _fail(str(exc))

    order = state["order"]
    by_id = state["by_id"]
    running = _in_progress_cid(order, by_id)
    if running is not None:
        unit = _unit_by_id(arc, running) or {}
        return _fail_json(
            {
                "ok": False,
                "error": "already_running",
                "chapter_id": running,
                "current": running,
                "leaf_id": unit.get("leaf_id") or (by_id.get(running) or {}).get("leaf_id"),
                "lens": unit.get("lens") or (by_id.get(running) or {}).get("lens"),
                "message": (
                    "chapter already in_progress; do not begin concurrently — "
                    "complete the current chapter first"
                ),
            },
            3,
        )

    nxt = next_chapter_id(order, by_id)
    if nxt is None:
        return _ok(
            {
                "ok": True,
                "command": "begin",
                "chapter_id": None,
                "status": "complete",
                "message": "all chapters done",
            }
        )

    unit = _unit_by_id(arc, nxt)
    if unit is None:
        return _fail(f"write unit missing for chapter {nxt!r}")

    entry = by_id[nxt]
    entry["status"] = "in_progress"
    entry["started_at"] = entry.get("started_at") or _now()
    entry["leaf_id"] = unit["leaf_id"]
    entry["lens"] = unit["lens"]
    state["current"] = nxt
    state["status"] = compute_top_status(order, by_id)
    state["updated_at"] = _now()
    save_chapter_write_state(path, state)
    return _ok(
        {
            "ok": True,
            "command": "begin",
            "chapter_id": nxt,
            "leaf_id": unit["leaf_id"],
            "leaf_title": unit.get("leaf_title") or "",
            "lens": unit["lens"],
            "fact_ids": list(unit.get("fact_ids") or []),
            "status": "in_progress",
        }
    )


def cmd_complete(args: argparse.Namespace) -> int:
    """Complete the claimed current chapter (optional --chapter must match)."""
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
    running = _in_progress_cid(order, by_id)
    if running is None:
        return _fail_json(
            {
                "ok": False,
                "error": "not_in_progress",
                "message": "no chapter in_progress; call begin first",
            },
            5,
        )

    requested = str(getattr(args, "chapter", None) or "").strip()
    if requested and requested != running:
        return _fail_json(
            {
                "ok": False,
                "error": "chapter_mismatch",
                "current": running,
                "requested": requested,
                "message": "complete targets current in_progress chapter only",
            },
            2,
        )

    cid = running
    idx = order.index(cid)
    for prev in order[:idx]:
        if str(by_id[prev].get("status")) != "done":
            return _fail_json(
                {"ok": False, "error": "gate_failed", "blocker": prev},
                3,
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
            "chapter_id": cid,
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

    p_status = sub.add_parser("status", help="Show write-state progress (observe only)")
    add_rev(p_status)
    p_status.set_defaults(func=cmd_status)

    p_begin = sub.add_parser(
        "begin",
        help="Claim current chapter work ticket (no --chapter)",
    )
    add_rev(p_begin)
    # Reject if passed: claim-current forbids AI-selected cid.
    p_begin.add_argument(
        "--chapter",
        default=None,
        help=argparse.SUPPRESS,
    )
    p_begin.set_defaults(func=cmd_begin)

    p_complete = sub.add_parser(
        "complete",
        help="Complete current in_progress chapter (optional --chapter must match)",
    )
    add_rev(p_complete)
    p_complete.add_argument(
        "--chapter",
        default=None,
        help="Optional; must equal current in_progress chapter if set",
    )
    p_complete.set_defaults(func=cmd_complete)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
