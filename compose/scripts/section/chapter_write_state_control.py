#!/usr/bin/env python3
"""Control for archive-5.0 ``_chapter-write-state.json`` (claim-current serial Write).

Subcommands:
    sync       Align state order to narrative-arc write units
    status     Print next / done_count / status (observe only)
    begin      Claim current chapter (no --chapter); return work ticket
               (requires --project-root; optional --cycle-id)
    complete   Artifact gate + mark current done; advance next

``begin`` returns ticket fields plus ``writing_cognition`` and ``lens_intent``.
Arc I/O uses slice ``_narrative-arc.json`` only (no --arc-path in this wave).

CLI: ``python3 chapter_write_state_control.py --help``

Process how:
docs/domain/archive/compose/archive-5.0/compose-chapter-write-claim-current-design.md
docs/domain/archive/compose/archive-5.0/compose-chapter-write-begin-facts-ticket-design.md
docs/domain/archive/compose/archive-26.0/chapter-write-runner-extract-design.md
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

from chapter_artifact_paths import chapter_body_path  # noqa: E402
from chapter_fc_gates import check_chapter_write_artifacts  # noqa: E402
from chapter_write_state_schema import (  # noqa: E402
    chapter_write_state_path,
    compute_top_status,
    load_chapter_write_state,
    next_chapter_id,
    save_chapter_write_state,
)
from l_ledger_schema import active_slice_dir  # noqa: E402
from facts_schema import facts_path, load_facts  # noqa: E402
from load_compose_template import load_compose_template  # noqa: E402
from section_form_registry_schema import fetch_section_form_registry  # noqa: E402
from section_registry_schema import fetch_section_registry  # noqa: E402
from workflow_paths import resolve_revision_runtime_profile  # noqa: E402
from logs.workflow_log import emit_biz  # noqa: E402
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


def _assemble_ticket_facts(
    slice_dir: Path,
    fact_ids: list[str],
) -> tuple[list[dict[str, Any]] | None, list[str]]:
    """Build begin ticket ``facts`` in ``fact_ids`` order.

    Returns ``(facts, [])`` on success, or ``(None, missing_ids)`` when any id
    is absent from slice ``_facts.json``.
    """
    store = load_facts(facts_path(slice_dir))
    by_id = {str(item["id"]): item for item in store}
    missing = [fid for fid in fact_ids if fid not in by_id]
    if missing:
        return None, missing
    ticket: list[dict[str, Any]] = []
    for fid in fact_ids:
        src = by_id[fid]
        # Always emit anchors (empty list when absent) so writers do not
        # misread a missing key as a dropped field and bypass begin.
        anchors = src.get("anchors") or []
        ticket.append(
            {
                "id": src["id"],
                "text": src["text"],
                "anchors": list(anchors),
            }
        )
    return ticket, []


def _load_arc(slice_dir: Path) -> dict[str, Any]:
    return load_narrative_arc(narrative_arc_path(slice_dir))


def _fetch_json_role(
    role: str,
    *,
    project_root: Path,
    profile: str,
    cycle_id: str,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    if role == "section-registry":
        return fetch_section_registry(
            project_root,
            profile_id=profile,
            cycle_id=cycle_id or None,
            profile_path=profile_path,
        )
    if role == "section-form-registry":
        return fetch_section_form_registry(
            project_root,
            profile_id=profile,
            cycle_id=cycle_id or None,
            profile_path=profile_path,
        )
    raw = load_compose_template(
        role,
        project_root,
        profile_id=profile,
        cycle_id=cycle_id or None,
        profile_path=profile_path,
    )
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{role} must be a JSON object")
    return data


def _lens_section(registry: dict[str, Any], lens: str, *, role: str) -> dict[str, Any]:
    sections = registry.get("sections")
    if not isinstance(sections, dict):
        raise ValueError(f"{role}.sections must be an object")
    key = str(lens or "").strip().upper()
    section = sections.get(key)
    if not isinstance(section, dict):
        # try exact key if registry uses mixed case
        section = sections.get(str(lens or "").strip())
    if not isinstance(section, dict):
        raise ValueError(f"{role} missing section for lens {key!r}")
    return section


def _writing_cognition_for_lens(
    *,
    lens: str,
    project_root: Path,
    profile: str,
    cycle_id: str,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    form = _fetch_json_role(
        "section-form-registry",
        project_root=project_root,
        profile=profile,
        cycle_id=cycle_id,
        profile_path=profile_path,
    )
    section = _lens_section(form, lens, role="section-form-registry")
    presentation = section.get("presentation")
    expression = section.get("expression")
    if not isinstance(presentation, dict):
        presentation = {}
    if not isinstance(expression, dict):
        expression = {}
    return {
        "reading_axis": str(section.get("reading_axis") or ""),
        "presentation": presentation,
        "expression": expression,
    }


def _lens_intent_for_lens(
    *,
    lens: str,
    project_root: Path,
    profile: str,
    cycle_id: str,
    profile_path: Path | None = None,
) -> dict[str, str]:
    registry = _fetch_json_role(
        "section-registry",
        project_root=project_root,
        profile=profile,
        cycle_id=cycle_id,
        profile_path=profile_path,
    )
    section = _lens_section(registry, lens, role="section-registry")
    intent = section.get("intent")
    if intent is None or (isinstance(intent, str) and not intent.strip()):
        intent = section.get("desc")
    return {
        "intent": str(intent or "").strip(),
        "intent_boundary": str(section.get("intent_boundary") or "").strip(),
    }


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

    fact_ids = [str(fid) for fid in (unit.get("fact_ids") or [])]
    try:
        ticket_facts, missing = _assemble_ticket_facts(slice_dir, fact_ids)
    except ValueError as exc:
        return _fail(str(exc))
    if missing:
        return _fail_json(
            {
                "ok": False,
                "error": "missing_fact_ids",
                "chapter_id": nxt,
                "fact_ids": fact_ids,
                "missing_fact_ids": missing,
                "message": (
                    "begin cannot claim chapter: fact_ids missing from "
                    "_facts.json; fix arc or facts before begin"
                ),
            },
            4,
        )

    root = Path(args.project_root).resolve()
    cycle_id = str(args.cycle_id or "").strip()
    try:
        runtime = resolve_revision_runtime_profile(
            Path(args.revision_dir),
            root,
            cycle_id=cycle_id or None,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _fail(str(exc))
    try:
        writing_cognition = _writing_cognition_for_lens(
            lens=str(unit["lens"]),
            project_root=root,
            profile=runtime.profile_id,
            cycle_id=cycle_id,
            profile_path=runtime.profile_path,
        )
        lens_intent = _lens_intent_for_lens(
            lens=str(unit["lens"]),
            project_root=root,
            profile=runtime.profile_id,
            cycle_id=cycle_id,
            profile_path=runtime.profile_path,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _fail(str(exc))

    entry = by_id[nxt]
    entry["status"] = "in_progress"
    entry["started_at"] = entry.get("started_at") or _now()
    entry["leaf_id"] = unit["leaf_id"]
    entry["lens"] = unit["lens"]
    state["current"] = nxt
    state["status"] = compute_top_status(order, by_id)
    state["updated_at"] = _now()
    save_chapter_write_state(path, state)
    conv_id = str(getattr(args, "conversation_id", "") or "").strip() or None
    emit_biz(
        component="chapter-write",
        event="begin",
        conversation_id=conv_id,
        project_root=root,
        detail={
            "chapter_id": nxt,
            "leaf_id": unit["leaf_id"],
            "lens": unit["lens"],
        },
    )
    return _ok(
        {
            "ok": True,
            "command": "begin",
            "chapter_id": nxt,
            "leaf_id": unit["leaf_id"],
            "leaf_title": unit.get("leaf_title") or "",
            "lens": unit["lens"],
            "fact_ids": fact_ids,
            "facts": ticket_facts,
            "writing_cognition": writing_cognition,
            "lens_intent": lens_intent,
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

    body_path = chapter_body_path(slice_dir, cid)
    body_mtime = datetime.fromtimestamp(
        body_path.stat().st_mtime, tz=timezone.utc
    ).isoformat()

    by_id[cid]["status"] = "done"
    by_id[cid]["completed_at"] = _now()
    nxt = next_chapter_id(order, by_id)
    state["current"] = nxt
    state["status"] = compute_top_status(order, by_id)
    state["updated_at"] = _now()
    save_chapter_write_state(path, state)
    conv_id = str(getattr(args, "conversation_id", "") or "").strip() or None
    emit_biz(
        component="chapter-write",
        event="complete",
        conversation_id=conv_id,
        project_root=Path.cwd().resolve(),
        detail={
            "chapter_id": cid,
            "next": nxt,
            "status": state["status"],
            "body_path": str(body_path),
            "body_mtime": body_mtime,
        },
    )
    payload: dict[str, Any] = {
        "ok": True,
        "command": "complete",
        "chapter_id": cid,
        "next": nxt,
        "status": state["status"],
    }
    if state["status"] == "complete" and nxt is None:
        payload["message"] = "all chapters done"
    return _ok(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_rev(p: argparse.ArgumentParser) -> None:
        p.add_argument("--revision-dir", required=True)
        p.add_argument(
            "--conversation-id",
            default="",
            help="Conversation id for workflow biz logs (optional)",
        )

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
    p_begin.add_argument("--project-root", required=True)
    p_begin.add_argument(
        "--cycle-id",
        default="",
        help="Cycle id for framework template resolution",
    )
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
