#!/usr/bin/env python3
"""CLI for deductive-runner confirm-gate + quarantine-unref listing.

Subcommands:
    pending-init       Ensure pending store exists
    pending-add        Add an open pending item
    pending-resolve    Resolve an open item (resolved|escalated|out_of_scope)
    pending-list       List pending items (default: open only)
    quarantine-unref   List quarantined facts not cited by any other fact
    gate-check         Fail if pending missing, open items remain, or
                       unreferenced quarantine is unsettled

Design rationale (source repo, why-only):
docs/domain/archive/compose/archive-3.0/compose-deductive-runner-architecture-design.md §4.5.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_DEDUCTIVE = Path(__file__).resolve().parent
_SCRIPTS = _DEDUCTIVE.parent
_SECTION = _SCRIPTS / "section"
for p in (_SCRIPTS, _SECTION, _DEDUCTIVE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from deductive_gate import evaluate_deductive_gate  # noqa: E402
from deductive_pending_schema import (  # noqa: E402
    PENDING_KINDS,
    PENDING_STATUSES,
    empty_pending,
    load_pending,
    next_pending_id,
    open_items,
    pending_path,
    save_pending,
)
from facts_schema import (  # noqa: E402
    facts_path,
    load_facts,
    unlensed_fact_ids,
)
from derive_shell import collect_ref_tokens  # noqa: E402


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def cmd_pending_init(args: argparse.Namespace) -> int:
    path = pending_path(args.revision_dir.resolve())
    if path.is_file():
        data = load_pending(path)
    else:
        data = empty_pending()
        save_pending(path, data)
    return _ok(
        {
            "ok": True,
            "command": "pending-init",
            "path": path.as_posix(),
            "open_count": len(open_items(data)),
        }
    )


def cmd_pending_add(args: argparse.Namespace) -> int:
    path = pending_path(args.revision_dir.resolve())
    data = load_pending(path)
    kind = args.kind.strip().lower()
    if kind not in PENDING_KINDS:
        return _fail(f"kind must be one of {sorted(PENDING_KINDS)}")
    # Dedup open items by kind+lens+upstream_ref+summary
    for item in open_items(data):
        if (
            str(item.get("kind", "")).lower() == kind
            and str(item.get("lens", "")) == (args.lens or "")
            and str(item.get("upstream_ref", "")) == (args.upstream_ref or "")
            and str(item.get("summary", "")).strip() == args.summary.strip()
        ):
            return _ok(
                {
                    "ok": True,
                    "command": "pending-add",
                    "id": item["id"],
                    "deduped": True,
                }
            )
    item = {
        "id": next_pending_id(data["items"]),
        "kind": kind,
        "status": "open",
        "summary": args.summary.strip(),
        "lens": (args.lens or "").strip().upper(),
        "upstream_ref": (args.upstream_ref or "").strip(),
    }
    data["items"].append(item)
    try:
        save_pending(path, data)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "command": "pending-add", "id": item["id"], "deduped": False})


def cmd_pending_resolve(args: argparse.Namespace) -> int:
    path = pending_path(args.revision_dir.resolve())
    data = load_pending(path)
    status = args.status.strip().lower()
    if status not in PENDING_STATUSES - {"open"}:
        return _fail("status must be resolved|escalated|out_of_scope")
    pid = args.id.strip()
    found = False
    for item in data["items"]:
        if str(item.get("id", "")).strip() != pid:
            continue
        if str(item.get("status", "")).lower() != "open":
            return _fail(f"{pid} is not open")
        item["status"] = status
        if args.note:
            item["note"] = args.note.strip()
        found = True
        break
    if not found:
        return _fail(f"pending id not found: {pid}")
    try:
        save_pending(path, data)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "command": "pending-resolve", "id": pid, "status": status})


def cmd_pending_list(args: argparse.Namespace) -> int:
    path = pending_path(args.revision_dir.resolve())
    data = load_pending(path)
    items = data["items"]
    if not args.all:
        items = open_items(data)
    return _ok(
        {
            "ok": True,
            "command": "pending-list",
            "items": items,
            "open_count": len(open_items(data)),
        }
    )


def cmd_quarantine_unref(args: argparse.Namespace) -> int:
    revision_dir = args.revision_dir.resolve()
    try:
        facts = load_facts(facts_path(revision_dir))
    except ValueError as exc:
        return _fail(str(exc))
    cited: set[str] = set()
    for fact in facts:
        cited |= collect_ref_tokens(fact)
    unref = [fid for fid in unlensed_fact_ids(facts) if fid not in cited]
    return _ok(
        {
            "ok": True,
            "command": "quarantine-unref",
            "unreferenced_ids": unref,
            "quarantined_total": len(unlensed_fact_ids(facts)),
        }
    )


def cmd_gate_check(args: argparse.Namespace) -> int:
    rev = args.revision_dir.resolve()
    reason = evaluate_deductive_gate(rev)
    if reason:
        return _fail(reason)
    data = load_pending(pending_path(rev))
    return _ok(
        {
            "ok": True,
            "command": "gate-check",
            "open_count": 0,
            "items_total": len(data.get("items") or []),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision-dir", type=Path, required=True)
    parser.add_argument("--profile", type=str, default="")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("pending-init", help="Ensure pending store exists")
    p_init.set_defaults(func=cmd_pending_init)

    p_add = sub.add_parser("pending-add", help="Add open pending item")
    p_add.add_argument("--kind", required=True, help=f"one of {sorted(PENDING_KINDS)}")
    p_add.add_argument("--summary", required=True)
    p_add.add_argument("--lens", default="")
    p_add.add_argument("--upstream-ref", default="")
    p_add.set_defaults(func=cmd_pending_add)

    p_res = sub.add_parser("pending-resolve", help="Resolve open pending item")
    p_res.add_argument("--id", required=True)
    p_res.add_argument("--status", required=True)
    p_res.add_argument("--note", default="")
    p_res.set_defaults(func=cmd_pending_resolve)

    p_list = sub.add_parser("pending-list", help="List pending items")
    p_list.add_argument("--all", action="store_true", help="Include non-open items")
    p_list.set_defaults(func=cmd_pending_list)

    p_q = sub.add_parser(
        "quarantine-unref",
        help="List quarantined facts not cited by any fact refs",
    )
    p_q.set_defaults(func=cmd_quarantine_unref)

    p_gate = sub.add_parser("gate-check", help="Fail if open pending remain")
    p_gate.set_defaults(func=cmd_gate_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
