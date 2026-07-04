#!/usr/bin/env python3
"""Inductive grounding receipt control (Gate 3 shallow grounding subagent output).

Persists distilled grounding facts to grounding-notes.json. Shallow grounding
for a sweep must run in a dispatched subagent — record-grounding rejects calls
from the orchestrating parent conversation on Cursor (SUBAGENT_REQUIRED).

Subcommands:
    unsettled-sections   List unsettled coverage sections + frontier_kw
    record-grounding     Append one or more receipts (--json object or array)
    list-grounding       List receipts for a sweep (--sweep required)
    check-grounding      Verify every unsettled section has a receipt (--sweep)

All subcommands print JSON to stdout; exit 0 on success, exit 1 on failure.
Global flags: --out-dir PATH (required). Platform session identity is hook-managed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from active_context_schema import resolve_conversation_id  # noqa: E402
from inductive_gate_state_schema import load_gate_state  # noqa: E402
from inductive_grounding_schema import (  # noqa: E402
    append_receipts,
    check_sweep_coverage,
    grounding_notes_path,
    init_ledger,
    load_ledger,
    receipts_for_sweep,
    save_ledger,
)
from inductive_section_pointer_schema import DONE_STATUSES, load_section_pointer  # noqa: E402
from platform_schema import detect_platform  # noqa: E402

_SUBAGENT_REQUIRED_PREFIX = "SUBAGENT_REQUIRED:"
_MASTER_CONVERSATION_REQUIRED_PREFIX = "MASTER_CONVERSATION_REQUIRED:"
_CONVERSATION_ID_REQUIRED_PREFIX = "CONVERSATION_ID_REQUIRED:"


def _ok(payload: dict[str, Any]) -> None:
    print(json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False))


def _fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}, indent=2, ensure_ascii=False))
    sys.exit(1)


def _gate_state_path(out_dir: Path) -> Path:
    return out_dir / "inductive-gate-state.json"


def _load_unsettled_sections(out_dir: Path) -> list[dict[str, Any]]:
    ptr_path = out_dir / "inductive-section-pointer.json"
    pointer = load_section_pointer(ptr_path)
    result: list[dict[str, Any]] = []
    for key in pointer["coverage_order"]:
        entry = pointer["sections"].get(key, {})
        status = str(entry.get("status", "untouched")).lower()
        if status in DONE_STATUSES:
            continue
        result.append(
            {
                "section": key,
                "status": status,
                "frontier_kw": entry.get("frontier_kw", 0),
            }
        )
    return result


def _load_master_conversation_id(out_dir: Path) -> str:
    gate_path = _gate_state_path(out_dir)
    if not gate_path.exists():
        return ""
    try:
        state = load_gate_state(gate_path)
    except (FileNotFoundError, ValueError):
        return ""
    return str(state.get("master_conversation_id", "")).strip()


def _check_subagent_dispatch(out_dir: Path, conversation_id: str) -> None:
    """Reject record-grounding when invoked from the orchestrating parent."""
    if detect_platform() != "cursor":
        return

    master = _load_master_conversation_id(out_dir)
    if not master:
        raise ValueError(
            f"{_MASTER_CONVERSATION_REQUIRED_PREFIX} init-session must complete "
            "before record-grounding. Re-run $INDUCTIVE_GATE_CTL init-session, "
            "then dispatch g3-shallow-grounding-runner."
        )

    conv_id = resolve_conversation_id(conversation_id)
    if not conv_id:
        raise ValueError(
            f"{_CONVERSATION_ID_REQUIRED_PREFIX} record-grounding failed: "
            "caller session identity missing; retry via dispatched subagent."
        )

    if master == conv_id:
        raise ValueError(
            f"{_SUBAGENT_REQUIRED_PREFIX} shallow grounding must run in a dispatched "
            "g3-shallow-grounding-runner subagent via $SUBAGENT_TOOL "
            "(run_in_background: false). Do not record grounding inline from the "
            "orchestrating conversation. Dispatch the subagent and retry."
        )


def cmd_unsettled_sections(out_dir: Path, _args: argparse.Namespace) -> None:
    try:
        sections = _load_unsettled_sections(out_dir)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))
    _ok({"unsettled": sections, "count": len(sections)})


def cmd_record_grounding(out_dir: Path, args: argparse.Namespace) -> None:
    try:
        _check_subagent_dispatch(out_dir, args.conversation_id or "")
    except ValueError as exc:
        _fail(str(exc))

    if not args.json:
        _fail("--json is required")

    try:
        payload = json.loads(args.json)
    except json.JSONDecodeError as exc:
        _fail(f"invalid --json: {exc}")

    if isinstance(payload, dict):
        receipts = [payload]
    elif isinstance(payload, list):
        receipts = payload
    else:
        _fail("--json must be a JSON object or array of objects")

    for receipt in receipts:
        if not isinstance(receipt, dict):
            _fail("each receipt must be a JSON object")
        receipt.setdefault("produced_by", "subagent")
        receipt.setdefault("mode", "shallow")
        if args.sweep is not None:
            receipt.setdefault("sweep", args.sweep)

    path = grounding_notes_path(out_dir)
    ledger = load_ledger(path)
    try:
        updated = append_receipts(ledger, receipts)
    except ValueError as exc:
        _fail(str(exc))

    save_ledger(path, updated)
    ids = [r["id"] for r in updated["receipts"][-len(receipts) :]]
    _ok({"recorded": ids, "count": len(ids)})


def cmd_list_grounding(out_dir: Path, args: argparse.Namespace) -> None:
    if args.sweep is None:
        _fail("--sweep is required")
    path = grounding_notes_path(out_dir)
    try:
        ledger = load_ledger(path)
    except ValueError as exc:
        _fail(str(exc))
    mode = args.mode or "shallow"
    receipts = receipts_for_sweep(ledger, args.sweep, mode=mode)
    _ok({"sweep": args.sweep, "mode": mode, "receipts": receipts, "count": len(receipts)})


def cmd_check_grounding(out_dir: Path, args: argparse.Namespace) -> None:
    if args.sweep is None:
        _fail("--sweep is required")
    mode = args.mode or "shallow"
    try:
        unsettled = _load_unsettled_sections(out_dir)
        ledger = load_ledger(grounding_notes_path(out_dir))
        result = check_sweep_coverage(
            ledger, args.sweep, unsettled, mode=mode
        )
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))

    if not result["ok"]:
        _fail("; ".join(result["errors"]) or "grounding check failed")

    _ok(result)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out-dir", required=True, metavar="PATH")
    parser.add_argument(
        "--conversation-id",
        default="",
        help="Injected by hook_guard on Cursor; used for SUBAGENT_REQUIRED gate",
    )

    sub = parser.add_subparsers(dest="subcommand", required=True)

    sub.add_parser("unsettled-sections", help="List unsettled sections + frontier_kw")

    p = sub.add_parser("record-grounding", help="Append grounding receipt(s)")
    p.add_argument("--json", required=True, metavar="JSON")
    p.add_argument("--sweep", type=int, default=None, help="Default sweep for receipts")

    p = sub.add_parser("list-grounding", help="List receipts for one sweep")
    p.add_argument("--sweep", type=int, required=True)
    p.add_argument("--mode", default="shallow", choices=["shallow", "deep", "g2"])

    p = sub.add_parser("check-grounding", help="Verify sweep coverage for unsettled sections")
    p.add_argument("--sweep", type=int, required=True)
    p.add_argument("--mode", default="shallow", choices=["shallow", "deep", "g2"])

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dispatch = {
        "unsettled-sections": cmd_unsettled_sections,
        "record-grounding": cmd_record_grounding,
        "list-grounding": cmd_list_grounding,
        "check-grounding": cmd_check_grounding,
    }
    handler = dispatch.get(args.subcommand)
    if handler is None:
        _fail(f"unknown subcommand: {args.subcommand!r}")
    handler(out_dir, args)


if __name__ == "__main__":
    main()
