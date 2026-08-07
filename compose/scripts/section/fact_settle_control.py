#!/usr/bin/env python3
"""Fact-settle control (archive-10.0 T2).

Split confirmed conclusions into proposed facts (shown in dialogue — no
staging file). Human confirm|cancel is whole-batch. Writes only via
``commit --confirm``. Proposed facts arrive via ``--facts-json`` or stdin
only (no ``--facts-file`` staging transport).

Subcommands: commit · cancel

On successful commit, returns ``stale_signal`` / ``suggest_check`` for
optional narrative-arc regenerate (T3).

CLI: ``python3 fact_settle_control.py --help``

Process how: docs/domain/archive/compose/archive-10.0/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from discussion_pointer_schema import active_slice_dir  # noqa: E402
from facts_schema import facts_path, load_facts, save_facts  # noqa: E402


def _slice(revision_dir: str) -> Path:
    return active_slice_dir(Path(revision_dir).resolve())


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _next_fact_id(facts: list[dict[str, Any]]) -> int:
    max_n = 0
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        fid = str(fact.get("id", ""))
        if fid.startswith("F-"):
            try:
                max_n = max(max_n, int(fid[2:]))
            except ValueError:
                continue
    return max_n + 1


def _load_entries(args: argparse.Namespace) -> list[dict[str, Any]]:
    # T2: proposed batch stays in dialogue / CLI args — no staging file transport
    if args.facts_json:
        raw = args.facts_json
    else:
        raw = sys.stdin.read()
    data = json.loads(raw)
    if not isinstance(data, list) or not data:
        raise ValueError("facts must be a non-empty JSON array")
    return data


def cmd_commit(args: argparse.Namespace) -> int:
    if not args.confirm:
        return _fail("commit requires --confirm (whole-batch human confirm)")
    slice_dir = _slice(args.revision_dir)
    path = facts_path(slice_dir)
    try:
        entries = _load_entries(args)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return _fail(f"cannot read proposed facts: {exc}")

    existing = load_facts(path) if path.is_file() else []
    facts = list(existing)
    n = _next_fact_id(facts)
    written: list[str] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            return _fail(f"facts[{i}] must be an object")
        text = str(entry.get("text") or "").strip()
        if not text:
            return _fail(f"facts[{i}]: text required")
        tags_raw = entry.get("lens_tags")
        if not isinstance(tags_raw, list):
            return _fail(f"facts[{i}]: lens_tags must be an array")
        lens_tags = [str(t).strip().upper() for t in tags_raw if str(t).strip()]
        if not lens_tags:
            return _fail(f"facts[{i}]: lens_tags must be non-empty")
        fact_id = f"F-{n}"
        fact: dict[str, Any] = {
            "id": fact_id,
            "text": text,
            "lens_tags": lens_tags,
            "origin": {
                "type": "discovered",
                "ref": [str(r) for r in (entry.get("origin_ref") or ["fact-settle"])],
            },
        }
        if entry.get("anchors") is not None:
            fact["anchors"] = entry["anchors"]
        facts.append(fact)
        written.append(fact_id)
        n += 1

    try:
        save_facts(path, facts)
    except ValueError as exc:
        return _fail(str(exc))

    return _ok(
        {
            "ok": True,
            "command": "commit",
            "path": str(path),
            "fact_ids": written,
            "facts_total": len(facts),
            "stale_signal": True,
            "suggest_check": True,
            "message": "facts committed; collab arc may be stale — suggest check / optional regenerate",
        }
    )


def cmd_cancel(args: argparse.Namespace) -> int:
    return _ok(
        {
            "ok": True,
            "command": "cancel",
            "written": False,
            "message": "whole batch cancelled; _facts.json unchanged",
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("commit", help="Whole-batch write after human confirm")
    p.add_argument("--revision-dir", required=True)
    p.add_argument(
        "--confirm",
        action="store_true",
        help="Required; mechanical gate for human whole-batch confirm",
    )
    p.add_argument(
        "--facts-json",
        default=None,
        help="JSON array of {text,lens_tags} (or pass the array on stdin)",
    )
    p.set_defaults(func=cmd_commit)

    p = sub.add_parser("cancel", help="Whole-batch cancel (no write)")
    p.add_argument("--revision-dir", required=True)
    p.set_defaults(func=cmd_cancel)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
