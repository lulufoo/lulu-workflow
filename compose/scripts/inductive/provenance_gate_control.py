#!/usr/bin/env python3
"""Gate G5 (Provenance) control for the inductive runner.

Find-and-name-only gate that runs after G4 and before inductive-complete.
It does NOT make semantic judgments — the SKILL-layer agent decides which
deviations exist and records them here; this control only moves gate state
and persists / presents the three provenance trace files.

Trace files (one per upstream role) live in --out-dir, sibling of
inductive-dqi.json:
    provenance-trace-intent.json  (intent-baseline)
    provenance-trace-scope.json   (scope)
    provenance-trace-norm.json    (norm-constraint)

Subcommands:
    init-session     Seed gate state + three empty trace files
    resolve-context  Return gate status + per-role delta counts (resume entry)
    record-delta     Append one named delta to a role's trace file
                      (must run in a dispatched g5-provenance-runner subagent)
    present          Read-only receipt: all deltas grouped by role
    gate-close       Require trace files exist, present summary, mark G5 closed

All subcommands print JSON to stdout; exit 0 on success, exit 1 on failure.
Global flag: --out-dir PATH (required). Platform session identity is hook-managed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from inductive_subagent_guard import require_subagent_dispatch  # noqa: E402
from provenance_trace_schema import (  # noqa: E402
    ROLES,
    append_delta,
    gate_state_path,
    load_gate_state,
    load_trace,
    new_gate_state,
    new_trace,
    save_gate_state,
    save_trace,
    trace_path,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok(payload: dict[str, Any]) -> None:
    print(json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False))


def _fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}, indent=2, ensure_ascii=False))
    sys.exit(1)


def _all_deltas(out_dir: Path) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for role in ROLES:
        path = trace_path(out_dir, role)
        grouped[role] = load_trace(path)["deltas"] if path.exists() else []
    return grouped


def cmd_init_session(out_dir: Path, args: argparse.Namespace) -> None:
    if gate_state_path(out_dir).exists():
        _fail(f"provenance gate state already exists: {gate_state_path(out_dir)}; use resolve-context")

    cycle_id = args.cycle_id or ""
    stage = args.stage or ""
    for role in ROLES:
        save_trace(
            trace_path(out_dir, role),
            new_trace(role=role, cycle_id=cycle_id, stage=stage),
        )
    save_gate_state(out_dir, new_gate_state(cycle_id=cycle_id, stage=stage))
    _ok({"message": "provenance gate initialized", "gate": "G5", "status": "active"})


def cmd_resolve_context(out_dir: Path, _args: argparse.Namespace) -> None:
    try:
        state = load_gate_state(out_dir)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))
    grouped = _all_deltas(out_dir)
    _ok({
        "gate": "G5",
        "status": state.get("status", "active"),
        "delta_counts": {role: len(deltas) for role, deltas in grouped.items()},
    })


def _build_delta(args: argparse.Namespace) -> dict[str, Any]:
    if args.json:
        try:
            delta = json.loads(args.json)
        except json.JSONDecodeError as exc:
            _fail(f"invalid --json: {exc}")
        if not isinstance(delta, dict):
            _fail("--json must be a JSON object")
        delta.setdefault("role", args.role)
        return delta
    code_refs = [c.strip() for c in (args.code_refs or "").split(",") if c.strip()]
    return {
        "id": args.id,
        "axis": args.axis,
        "role": args.role,
        "bucket": args.bucket,
        "section": args.section or None,
        "upstream_anchor": args.upstream_anchor,
        "description": args.description,
        "code_refs": code_refs,
        "blocking": str(args.blocking).strip().lower() != "false",
    }


def cmd_record_delta(out_dir: Path, args: argparse.Namespace) -> None:
    try:
        require_subagent_dispatch(
            out_dir,
            args.conversation_id or "",
            record_command="record-delta",
            runner_skill="g5-provenance-runner",
            operation_label="Gate 5 provenance scan",
        )
    except ValueError as exc:
        _fail(str(exc))

    try:
        state = load_gate_state(out_dir)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))
    if state.get("status") == "closed":
        _fail("cannot record delta: G5 already closed")

    role = args.role
    if role not in ROLES:
        _fail(f"invalid role: {role!r}; must be one of {list(ROLES)}")
    path = trace_path(out_dir, role)
    try:
        data = load_trace(path) if path.exists() else new_trace(role=role)
        updated = append_delta(data, _build_delta(args))
        save_trace(path, updated)
    except (ValueError, FileNotFoundError) as exc:
        _fail(str(exc))
    _ok({"recorded": args.id, "role": role, "count": len(updated["deltas"])})


def cmd_present(out_dir: Path, _args: argparse.Namespace) -> None:
    grouped = _all_deltas(out_dir)
    total = sum(len(v) for v in grouped.values())
    _ok({
        "gate": "G5",
        "total_deltas": total,
        "deltas": grouped,
    })


def cmd_gate_close(out_dir: Path, _args: argparse.Namespace) -> None:
    try:
        state = load_gate_state(out_dir)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))
    if state.get("status") == "closed":
        _fail("G5 is already closed")

    missing = [role for role in ROLES if not trace_path(out_dir, role).exists()]
    if missing:
        _fail(f"missing trace file(s) for role(s): {missing}; run init-session")

    grouped = _all_deltas(out_dir)
    total = sum(len(v) for v in grouped.values())

    state["status"] = "closed"
    state["closed_at"] = _now_iso()
    save_gate_state(out_dir, state)

    _ok({
        "closed": "G5",
        "total_deltas": total,
        "delta_counts": {role: len(deltas) for role, deltas in grouped.items()},
        "deltas": grouped,
        "note": "find-and-name only; all deltas are pending-signoff (sign-off is a later phase)",
    })


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out-dir", required=True, metavar="PATH",
                        help="$INDUCTIVE_OUT_DIR: revision dir for trace + gate state files")
    parser.add_argument(
        "--conversation-id",
        default="",
        help="Injected by hook_guard on Cursor; used for SUBAGENT_REQUIRED gate",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p = sub.add_parser("init-session", help="Seed gate state + empty trace files")
    p.add_argument("--cycle-id", default="", help="Cycle id for traceability")
    p.add_argument("--stage", default="", help="Compose stage id (e.g. lulu-design)")

    sub.add_parser("resolve-context", help="Return gate status + per-role delta counts")

    p = sub.add_parser("record-delta", help="Append one named delta to a role's trace")
    p.add_argument("--role", required=True, help="intent-baseline | scope | norm-constraint")
    p.add_argument("--id", default="", help="Unique delta id within the role trace")
    p.add_argument("--axis", type=int, default=0, help="1 (overreach/conflict) | 2 (coverage)")
    p.add_argument("--bucket", default="", help="Deviation bucket (see mechanism SSOT)")
    p.add_argument("--section", default="", help="Axis-1 section key; omit for axis 2")
    p.add_argument("--upstream-anchor", default="", help="Excerpt of the conflicting upstream clause")
    p.add_argument("--description", default="", help="Human-readable delta description")
    p.add_argument("--code-refs", default="", help="Comma-separated code references")
    p.add_argument("--blocking", default="true", help="true|false (default true)")
    p.add_argument("--json", default="", metavar="JSON", help="Full delta object (overrides flags)")

    sub.add_parser("present", help="Read-only receipt: all deltas grouped by role")
    sub.add_parser("gate-close", help="Present summary and mark G5 closed")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dispatch = {
        "init-session": cmd_init_session,
        "resolve-context": cmd_resolve_context,
        "record-delta": cmd_record_delta,
        "present": cmd_present,
        "gate-close": cmd_gate_close,
    }
    handler = dispatch.get(args.subcommand)
    if handler is None:
        _fail(f"unknown subcommand: {args.subcommand!r}")
    handler(out_dir, args)


if __name__ == "__main__":
    main()
