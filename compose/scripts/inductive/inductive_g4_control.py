#!/usr/bin/env python3
"""Gate 4 internal-audit report control (recompose-runner output).

Persists one g4-recompose-report.json on the working slice. The report binds
facts/opens digests and findings; it does not copy the fact list.

record-recompose-report is parent-legal. The analysis runner stays
read-only; the parent records the structured return.

Subcommands:
    audit-context             Return facts/opens snapshots + digests
    record-recompose-report   Overwrite g4-recompose-report.json (--json object)
    check-recompose-report    Validate report schema + closability
    list-recompose-report     Return findings, predicates, and digests
    delete-recompose-report   Delete g4-recompose-report.json

All subcommands print JSON to stdout; exit 0 on success, exit 1 on failure.
Global flags: --out-dir PATH (required). Platform session identity is hook-managed.

Design rationale:
docs/domain/archive/compose/archive-37.0/compose-g3-detect-execution-closure-design.md
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

_COMPOSE_SCRIPTS = _HERE.parent
_SESSION = _COMPOSE_SCRIPTS / "schema" / "session"
_KERNEL = _COMPOSE_SCRIPTS / "_kernel"
_SCHEMA_DIRS = (
    _HERE / "schema" / "gate",
    _HERE / "schema" / "g2",
    _HERE / "schema" / "g3",
    _HERE / "schema" / "g4",
)
for _path in (_SESSION, _KERNEL, *_SCHEMA_DIRS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from compose_state_lock import canonical_digest, compose_state_lock  # noqa: E402
from g4_recompose_report_schema import (  # noqa: E402
    check_report_readable,
    delete_report,
    g4_report_path,
    load_report,
    save_report,
    validate_finding_lens_sources,
)
from l_ledger_schema import working_slice_dir  # noqa: E402
from open_point_store import facts_snapshot  # noqa: E402
from opens_schema import load_opens, opens_path  # noqa: E402


def _ok(payload: dict[str, Any]) -> None:
    print(json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False))


def _fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}, indent=2, ensure_ascii=False))
    sys.exit(1)


def _slice_dir(out_dir: Path) -> Path:
    return working_slice_dir(Path(out_dir))


def _current_digests(slice_dir: Path) -> tuple[Any, list[dict[str, Any]], str, str]:
    facts = facts_snapshot(slice_dir)
    if not isinstance(facts, list):
        facts = []
    opens = load_opens(opens_path(slice_dir))
    return facts, opens, canonical_digest(facts), canonical_digest(opens)


def _report_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    report = dict(payload)
    echoed = report.get("echoed_digests")
    if isinstance(echoed, dict):
        report.setdefault(
            "facts_digest", echoed.get("facts_digest") or echoed.get("facts")
        )
        report.setdefault(
            "opens_digest", echoed.get("opens_digest") or echoed.get("opens")
        )
        report.pop("echoed_digests", None)
    findings = report.get("findings")
    if isinstance(findings, list):
        cleaned: list[dict[str, Any]] = []
        for item in findings:
            if not isinstance(item, dict):
                cleaned.append(item)
                continue
            finding = {
                "question": item.get("question"),
                "basis": item.get("basis") or item.get("evidence"),
                "blocking": item.get("blocking", True),
                "lens": item.get("lens"),
            }
            cleaned.append(finding)
        report["findings"] = cleaned
    report.setdefault("produced_by", "subagent")
    return report


def cmd_audit_context(out_dir: Path, _args: argparse.Namespace) -> None:
    slice_dir = _slice_dir(out_dir)
    facts, opens, facts_digest, opens_digest = _current_digests(slice_dir)
    _ok(
        {
            "facts_snapshot": facts,
            "facts_digest": facts_digest,
            "opens_snapshot": opens,
            "opens_digest": opens_digest,
        }
    )


def cmd_record_recompose_report(out_dir: Path, args: argparse.Namespace) -> None:
    if not args.json:
        _fail("--json is required")
    try:
        payload = json.loads(args.json)
    except json.JSONDecodeError as exc:
        _fail(f"invalid --json: {exc}")
    if not isinstance(payload, dict):
        _fail("--json must be a JSON object")

    report = _report_from_payload(payload)
    slice_dir = _slice_dir(out_dir)
    with compose_state_lock(slice_dir):
        facts, opens, facts_digest, opens_digest = _current_digests(slice_dir)
        if (
            report.get("facts_digest") != facts_digest
            or report.get("opens_digest") != opens_digest
        ):
            _fail("stale facts/opens digest")
        source_errors = validate_finding_lens_sources(
            report.get("findings"), facts, opens
        )
        if source_errors:
            _fail("; ".join(source_errors))
        try:
            saved = save_report(g4_report_path(slice_dir), report)
        except ValueError as exc:
            _fail(str(exc))
    _ok(
        {
            "written": g4_report_path(slice_dir).name,
            "findings": saved["findings"],
            "facts_digest": saved["facts_digest"],
            "opens_digest": saved["opens_digest"],
            "report_digest": canonical_digest(saved),
        }
    )


def cmd_check_recompose_report(out_dir: Path, _args: argparse.Namespace) -> None:
    path = g4_report_path(_slice_dir(out_dir))
    if not path.exists():
        _fail("g4-recompose-report.json missing; dispatch recompose-runner first")
    try:
        report = load_report(path)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))
    result = check_report_readable(report)
    if not result["schema_ok"]:
        _fail("; ".join(result["errors"]) or "invalid g4 recompose report")
    if not result["closable"]:
        reasons = []
        if result.get("findings"):
            reasons.append(f"{len(result['findings'])} finding(s) remain")
        if not result.get("buildable"):
            reasons.append("buildable=false")
        if not result.get("reversible"):
            reasons.append("reversible=false")
        if not result.get("verifiable"):
            reasons.append("verifiable=false")
        _fail("; ".join(reasons) or "g4 recompose report not closable")
    _ok(result)


def cmd_list_recompose_report(out_dir: Path, _args: argparse.Namespace) -> None:
    path = g4_report_path(_slice_dir(out_dir))
    if not path.exists():
        _fail("g4-recompose-report.json missing; dispatch recompose-runner first")
    try:
        report = load_report(path)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))
    _ok(
        {
            "findings": report.get("findings", []),
            "buildable": report.get("buildable"),
            "reversible": report.get("reversible"),
            "verifiable": report.get("verifiable"),
            "facts_digest": report.get("facts_digest"),
            "opens_digest": report.get("opens_digest"),
            "report_digest": canonical_digest(report),
        }
    )


def cmd_delete_recompose_report(out_dir: Path, _args: argparse.Namespace) -> None:
    deleted = delete_report(_slice_dir(out_dir))
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
        help="Injected by hook_guard on Cursor; unused for record",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)
    sub.add_parser("audit-context", help="Return facts/opens snapshots + digests")
    p = sub.add_parser("record-recompose-report", help="Overwrite g4-recompose-report.json")
    p.add_argument("--json", required=True, metavar="JSON")
    sub.add_parser("check-recompose-report", help="Validate report; fail if not closable")
    sub.add_parser("list-recompose-report", help="Return findings, predicates, digests")
    sub.add_parser("delete-recompose-report", help="Delete g4-recompose-report.json")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dispatch = {
        "audit-context": cmd_audit_context,
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
