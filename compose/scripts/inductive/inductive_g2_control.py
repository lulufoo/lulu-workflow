#!/usr/bin/env python3
"""Gate 2 topology report control (g2-grounding-runner subagent output).

Persists a single g2-topology-report.json per session. record-g2-report must
run in a dispatched subagent — parent inline calls fail SUBAGENT_REQUIRED on Cursor.

Subcommands:
    record-g2-report   Overwrite g2-topology-report.json (--json object)
    check-g2-report    Validate report schema; ok=false when verdict!=ok
    list-g2-report     Return verdict, facts, divergences, checklist
    delete-g2-report   Delete g2-topology-report.json (gate-reopen G1 only)

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

from g2_topology_report_schema import (  # noqa: E402
    check_report_readable,
    delete_report,
    g2_report_path,
    load_report,
    save_report,
)
from inductive_subagent_guard import require_subagent_dispatch  # noqa: E402


def _ok(payload: dict[str, Any]) -> None:
    print(json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False))


def _fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}, indent=2, ensure_ascii=False))
    sys.exit(1)


def cmd_record_g2_report(out_dir: Path, args: argparse.Namespace) -> None:
    try:
        require_subagent_dispatch(
            out_dir,
            args.conversation_id or "",
            record_command="record-g2-report",
            runner_skill="g2-grounding-runner",
            operation_label="Gate 2 topology check",
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
        save_report(g2_report_path(out_dir), payload)
    except ValueError as exc:
        _fail(str(exc))

    _ok({"written": str(g2_report_path(out_dir).name), "verdict": payload.get("verdict")})


def cmd_check_g2_report(out_dir: Path, _args: argparse.Namespace) -> None:
    path = g2_report_path(out_dir)
    if not path.exists():
        _fail("g2-topology-report.json missing; dispatch g2-grounding-runner first")

    try:
        report = load_report(path)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))

    result = check_report_readable(report)
    if not result["schema_ok"]:
        _fail("; ".join(result["errors"]) or "invalid g2 topology report")

    if not result["closable"]:
        _fail("; ".join(result["errors"]) or f"verdict is {result['verdict']!r}")

    _ok(result)


def cmd_list_g2_report(out_dir: Path, _args: argparse.Namespace) -> None:
    path = g2_report_path(out_dir)
    if not path.exists():
        _fail("g2-topology-report.json missing; dispatch g2-grounding-runner first")

    try:
        report = load_report(path)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))

    _ok(
        {
            "verdict": report.get("verdict"),
            "facts": report.get("facts", []),
            "divergences": report.get("divergences", []),
            "checklist": report.get("checklist", []),
        }
    )


def cmd_delete_g2_report(out_dir: Path, _args: argparse.Namespace) -> None:
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

    p = sub.add_parser("record-g2-report", help="Overwrite g2-topology-report.json")
    p.add_argument("--json", required=True, metavar="JSON")

    sub.add_parser("check-g2-report", help="Validate report; fail if not closable")
    sub.add_parser("list-g2-report", help="Return verdict, facts, divergences")
    sub.add_parser("delete-g2-report", help="Delete g2-topology-report.json")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dispatch = {
        "record-g2-report": cmd_record_g2_report,
        "check-g2-report": cmd_check_g2_report,
        "list-g2-report": cmd_list_g2_report,
        "delete-g2-report": cmd_delete_g2_report,
    }
    handler = dispatch.get(args.subcommand)
    if handler is None:
        _fail(f"unknown subcommand: {args.subcommand!r}")
    handler(out_dir, args)


if __name__ == "__main__":
    main()
