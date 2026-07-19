#!/usr/bin/env python3
"""Claim / orphan ledger control for decision-fact units (Steps 3–4).

Subcommands:
    ensure       Create/sync decision-fact-claims.json from scope_ref (decision-fact.json)
    check        D6 gate: claimed→settled∨deferred; expose unclaimed (--strict fails unclaimed)
    set-status   Mark one unit claimed|settled|deferred|unclaimed (Seed/Init co-batch)

scope_ref not a decision-fact.json → mode=prose_fallback (ok). Does not seed facts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
_SESSION = _SCRIPTS / "schema" / "session"
for _p in (_HERE, _SESSION, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from decision_fact_claim_schema import (  # noqa: E402
    CLAIM_STATUSES,
    claim_ledger_path,
    claim_report,
    ensure_claim_ledger,
    set_unit_status,
    sync_and_evaluate_claims,
)
from resolved_refs_schema import (  # noqa: E402
    has_resolved_refs,
    scope_decision_fact_path,
)


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _emit_error(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    return 1


def _decision_fact_path(revision_dir: Path) -> str | None:
    if not has_resolved_refs(revision_dir):
        return None
    return scope_decision_fact_path(revision_dir)


def cmd_ensure(revision_dir: Path) -> int:
    try:
        ledger = ensure_claim_ledger(
            revision_dir,
            decision_fact_path=_decision_fact_path(revision_dir),
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    report = claim_report(ledger)
    _emit(
        {
            "ok": True,
            "command": "ensure",
            "ledger_path": claim_ledger_path(revision_dir).as_posix(),
            **report,
        }
    )
    return 0


def cmd_check(revision_dir: Path, *, strict: bool) -> int:
    """D6 gate: claimed→settled∨deferred; unclaimed exposed (fail only with --strict)."""
    try:
        result = sync_and_evaluate_claims(
            revision_dir,
            decision_fact_path=_decision_fact_path(revision_dir),
            fail_on_unclaimed=bool(strict),
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))

    _emit(
        {
            "command": "check",
            "strict": bool(strict),
            **result,
        }
    )
    return 0 if result.get("gate_ok") else 1


def cmd_set_status(
    revision_dir: Path,
    *,
    unit_id: str,
    status: str,
    by: str,
    note: str,
) -> int:
    try:
        ledger = set_unit_status(
            revision_dir,
            unit_id,
            status,
            by=by,
            note=note,
        )
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))
    report = claim_report(ledger)
    _emit(
        {
            "ok": True,
            "command": "set-status",
            "unit_id": unit_id,
            "status": status,
            "ledger_path": claim_ledger_path(revision_dir).as_posix(),
            **report,
        }
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Decision-fact claim ledger control.")
    parser.add_argument(
        "--revision-dir",
        required=True,
        help="Compose revision directory (contains resolved-refs.json).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "ensure",
        help="Create/sync claim ledger from scope_ref when it is decision-fact.json.",
    )
    check = sub.add_parser(
        "check",
        help="Sync + D6 gate (claimed must be settled∨deferred; expose unclaimed).",
    )
    check.add_argument(
        "--strict",
        action="store_true",
        help="Also fail when unclaimed units remain (stricter than D6 default).",
    )
    set_status = sub.add_parser(
        "set-status",
        help="Mark one unit claimed|settled|deferred|unclaimed.",
    )
    set_status.add_argument("--unit-id", required=True, help="Decision-fact unit id.")
    set_status.add_argument(
        "--status",
        required=True,
        choices=sorted(CLAIM_STATUSES),
        help="New claim status.",
    )
    set_status.add_argument("--by", default="", help="Consumer stamp (e.g. seed).")
    set_status.add_argument("--note", default="", help="Optional note.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    revision_dir = Path(args.revision_dir).expanduser().resolve()
    if args.command == "ensure":
        return cmd_ensure(revision_dir)
    if args.command == "check":
        return cmd_check(revision_dir, strict=bool(args.strict))
    if args.command == "set-status":
        return cmd_set_status(
            revision_dir,
            unit_id=args.unit_id,
            status=args.status,
            by=args.by,
            note=args.note,
        )
    return _emit_error(f"unknown command: {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
