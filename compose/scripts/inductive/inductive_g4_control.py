#!/usr/bin/env python3
"""Gate 4 semantic recompose report control (g4-recompose-runner subagent output).

Persists a single g4-recompose-report.json per session — the four **semantic**
Gate 4 predicates (conflicts / buildable / reversible / verifiable). The two
**structural** predicates (reforms_shape / shape_absorbed) stay in
inductive_g3_section_control.py recompose-check and are merged with this
report only at gate-close G4 (inductive_gate_control.py).

record-recompose-report must run in a dispatched subagent — parent inline
calls fail SUBAGENT_REQUIRED on Cursor.

Subcommands:
    record-recompose-report   Overwrite g4-recompose-report.json (--json object)
    check-recompose-report    Validate report schema + closability
    list-recompose-report     Return conflicts, buildable, reversible, verifiable, facts
    delete-recompose-report   Delete g4-recompose-report.json (gate-reopen G3/G1 only)

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

from g4_recompose_report_schema import (  # noqa: E402
    check_report_readable,
    delete_report,
    g4_report_path,
    load_report,
    save_report,
)
from inductive_subagent_guard import require_subagent_dispatch  # noqa: E402


def _ok(payload: dict[str, Any]) -> None:
    print(json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False))


def _fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}, indent=2, ensure_ascii=False))
    sys.exit(1)


def cmd_record_recompose_report(out_dir: Path, args: argparse.Namespace) -> None:
    try:
        require_subagent_dispatch(
            out_dir,
            args.conversation_id or "",
            record_command="record-recompose-report",
            runner_skill="g4-recompose-runner",
            operation_label="Gate 4 semantic recompose audit",
        )
    except ValueError as exc:
        _fail(str(exc))

    if not args.json:
        _fail("--json is required")

    try:
        payload = json.loads(args.json)
    except json.JSONDecodeError as exc:
        _fail(f"invalid --json: {exc}")

    if not isinstance(payload, dict):
        _fail("--json must be a JSON object")

    payload.setdefault("produced_by", "subagent")

    try:
        save_report(g4_report_path(out_dir), payload)
    except ValueError as exc:
        _fail(str(exc))

    _ok({"written": str(g4_report_path(out_dir).name), "conflicts": len(payload.get("conflicts") or [])})


def cmd_check_recompose_report(out_dir: Path, _args: argparse.Namespace) -> None:
    path = g4_report_path(out_dir)
    if not path.exists():
        _fail("g4-recompose-report.json missing; dispatch g4-recompose-runner first")

    try:
        report = load_report(path)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))

    result = check_report_readable(report)
    if not result["schema_ok"]:
        _fail("; ".join(result["errors"]) or "invalid g4 recompose report")

    if not result["closable"]:
        reasons = []
        if result.get("conflicts"):
            reasons.append(f"{len(result['conflicts'])} unresolved conflict(s)")
        if not result.get("buildable"):
            reasons.append("buildable=false")
        if not result.get("reversible"):
            reasons.append("reversible=false")
        if not result.get("verifiable"):
            reasons.append("verifiable=false")
        _fail("; ".join(reasons) or "g4 recompose report not closable")

    _ok(result)


def cmd_list_recompose_report(out_dir: Path, _args: argparse.Namespace) -> None:
    path = g4_report_path(out_dir)
    if not path.exists():
        _fail("g4-recompose-report.json missing; dispatch g4-recompose-runner first")

    try:
        report = load_report(path)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))

    _ok(
        {
            "conflicts": report.get("conflicts", []),
            "buildable": report.get("buildable"),
            "reversible": report.get("reversible"),
            "verifiable": report.get("verifiable"),
            "facts": report.get("facts", []),
        }
    )


def cmd_delete_recompose_report(out_dir: Path, _args: argparse.Namespace) -> None:
    deleted = delete_report(out_dir)
    _ok({"deleted": deleted})


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

    p = sub.add_parser("record-recompose-report", help="Overwrite g4-recompose-report.json")
    p.add_argument("--json", required=True, metavar="JSON")

    sub.add_parser("check-recompose-report", help="Validate report; fail if not closable")
    sub.add_parser("list-recompose-report", help="Return conflicts, buildable, reversible, verifiable")
    sub.add_parser("delete-recompose-report", help="Delete g4-recompose-report.json")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dispatch = {
        "record-recompose-report": cmd_record_recompose_report,
        "check-recompose-report": cmd_check_recompose_report,
        "list-recompose-report": cmd_list_recompose_report,
        "delete-recompose-report": cmd_delete_recompose_report,
    }
    handler = dispatch.get(args.subcommand)
    if handler is None:
        _fail(f"unknown subcommand: {args.subcommand!r}")
    handler(out_dir, args)


if __name__ == "__main__":
    main()
