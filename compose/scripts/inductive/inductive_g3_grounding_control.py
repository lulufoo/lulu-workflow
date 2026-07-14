#!/usr/bin/env python3
"""Inductive grounding receipt control (Gate 3 shallow + deep grounding subagent output).

Persists distilled grounding facts to grounding-notes.json. Both shallow
(whole-sweep) and deep (single open point) grounding must run in a dispatched
subagent — record-grounding rejects calls from the orchestrating parent
conversation on Cursor (SUBAGENT_REQUIRED); the required runner_skill is
derived from each receipt's own `mode` field.

Subcommands:
    unsettled-sections   List unsettled coverage sections + frontier_kw
    record-grounding     Append one or more receipts of a single mode
                          (--json object or array; --sweep sets the default)
    list-grounding       List receipts for a sweep (--sweep required;
                          --mode shallow|deep|g2, default shallow;
                          --ep-id optionally narrows mode=deep to one point)
    check-grounding      Verify every unsettled section has a receipt (--sweep)
                          — shallow coverage predicate only, not meaningful
                          for mode=deep (single-point, not sweep-wide)

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

from g3_grounding_notes_schema import (  # noqa: E402
    append_receipts,
    check_sweep_coverage,
    grounding_notes_path,
    init_ledger,
    load_ledger,
    receipts_for_sweep,
    save_ledger,
)
from g3_section_pointer_schema import DONE_STATUSES, load_section_pointer  # noqa: E402
from inductive_subagent_guard import require_subagent_dispatch  # noqa: E402


def _ok(payload: dict[str, Any]) -> None:
    print(json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False))


def _fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}, indent=2, ensure_ascii=False))
    sys.exit(1)


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


def cmd_unsettled_sections(out_dir: Path, _args: argparse.Namespace) -> None:
    try:
        sections = _load_unsettled_sections(out_dir)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))
    _ok({"unsettled": sections, "count": len(sections)})


_MODE_RUNNER_SKILL = {
    "shallow": "g3-shallow-grounding-runner",
    "deep": "g3-deep-grounding-runner",
}


def cmd_record_grounding(out_dir: Path, args: argparse.Namespace) -> None:
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

    modes = {str(r.get("mode", "shallow")).lower() for r in receipts}
    if len(modes) != 1:
        _fail(f"record-grounding requires a single mode per call, got {sorted(modes)}")
    mode = next(iter(modes))
    runner_skill = _MODE_RUNNER_SKILL.get(mode)
    if runner_skill is None:
        _fail(f"no dispatch runner registered for mode {mode!r}")

    try:
        require_subagent_dispatch(
            out_dir,
            args.conversation_id or "",
            record_command="record-grounding",
            runner_skill=runner_skill,
            operation_label=f"{mode} grounding",
        )
    except ValueError as exc:
        _fail(str(exc))

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
    ep_id = getattr(args, "ep_id", None) or getattr(args, "open_id", None)
    receipts = receipts_for_sweep(ledger, args.sweep, mode=mode, ep_id=ep_id)
    _ok(
        {
            "sweep": args.sweep,
            "mode": mode,
            "ep_id": ep_id,
            "open_id": ep_id,
            "receipts": receipts,
            "count": len(receipts),
        }
    )


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
    p.add_argument("--ep-id", default=None, dest="ep_id", help="Filter to one open id (mode=deep; O-n)")
    p.add_argument(
        "--open-id",
        default=None,
        dest="open_id",
        help="Alias for --ep-id (K4 open id O-n)",
    )

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
