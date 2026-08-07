#!/usr/bin/env python3
"""Fact-production control (archive-11.0; inherits archive-10.0 T2).

Whole-batch conclusion→facts (``commit`` / ``cancel``) and open→facts
(``settle-open``). Human confirm is required for writes. Proposed conclusion
facts arrive via ``--facts-json`` or stdin only (no ``--facts-file`` staging
for ``commit``). ``settle-open`` keeps ``--facts-file`` for open settlement
batches and atomically commits facts + open status.

On successful write, returns ``stale_signal`` / ``suggest_check`` for optional
collab-arc regenerate.

Subcommands: commit · cancel · settle-open · update · delete

CLI: ``python3 fact_production_control.py --help``

Process how: docs/domain/archive/compose/archive-11.0/
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

_RUNNER_SCRIPTS = Path(__file__).resolve().parent
_COMPOSE = _RUNNER_SCRIPTS.parents[1]
_SCRIPTS = _COMPOSE / "scripts"
_INDUCTIVE = _SCRIPTS / "inductive"
for _p in (_SCRIPTS, _INDUCTIVE, _RUNNER_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from discussion_pointer_schema import active_slice_dir  # noqa: E402
from facts_schema import (  # noqa: E402
    facts_path,
    load_facts,
    save_facts,
    validate_facts,
)
from g3_section_pointer_schema import load_section_pointer  # noqa: E402
from opens_schema import load_opens, opens_path, save_opens, validate_opens  # noqa: E402


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
    if args.facts_json:
        raw = args.facts_json
    else:
        raw = sys.stdin.read()
    data = json.loads(raw)
    if not isinstance(data, list) or not data:
        raise ValueError("facts must be a non-empty JSON array")
    return data


def _allowed_lenses(slice_dir: Path) -> list[str]:
    ptr_path = slice_dir / "inductive-section-pointer.json"
    if not ptr_path.is_file():
        return []
    ptr = load_section_pointer(ptr_path)
    return [str(k).strip().upper() for k in ptr.get("coverage_order") or []]


def _find_open(
    opens: list[dict[str, Any]], open_id: str
) -> dict[str, Any] | None:
    return next((o for o in opens if o.get("id") == open_id), None)


def _clean_code_ref(ref: str) -> str:
    return re.sub(r"\s*\(\d+\)\s*$", "", ref.strip()).strip()


def _code_ref_segments(cleaned: str) -> list[str]:
    return [seg.strip() for seg in cleaned.split("::") if seg.strip()]


def _distribute_code_refs(
    undeclared: list[dict[str, Any]],
    code_refs: list[str],
) -> None:
    for ref in code_refs:
        cleaned = _clean_code_ref(ref)
        if not cleaned:
            continue
        segments = _code_ref_segments(cleaned)
        anchor = {"kind": "code_ref", "value": cleaned}
        for fact in undeclared:
            text = fact.get("text", "")
            if any(seg in text for seg in segments):
                anchors = fact.setdefault("anchors", [])
                if anchor not in anchors:
                    anchors.append(anchor)


def _save_facts_inductive(slice_dir: Path, facts: list[dict[str, Any]]) -> None:
    save_facts(
        facts_path(slice_dir),
        facts,
        allowed_lenses=_allowed_lenses(slice_dir) or None,
    )


def _commit_facts_then_opens(
    slice_dir: Path,
    *,
    facts_before: list[dict[str, Any]],
    facts_after: list[dict[str, Any]],
    opens_after: list[dict[str, Any]],
) -> str | None:
    """Validate both stores, write facts then opens; roll back facts if opens fails.

    Returns error message or None on success.
    """
    allowed = _allowed_lenses(slice_dir)
    ferrs = validate_facts(facts_after, allowed_lenses=allowed or None)
    if ferrs:
        return "; ".join(ferrs)
    oerrs = validate_opens(opens_after)
    if oerrs:
        return "; ".join(oerrs)

    try:
        _save_facts_inductive(slice_dir, facts_after)
    except (ValueError, OSError) as exc:
        return str(exc)

    try:
        save_opens(opens_path(slice_dir), opens_after)
    except (ValueError, OSError) as exc:
        try:
            fpath = facts_path(slice_dir)
            if facts_before:
                _save_facts_inductive(slice_dir, facts_before)
            elif fpath.is_file():
                fpath.unlink()
        except (ValueError, OSError) as rollback_exc:
            return (
                f"opens save failed ({exc}); facts rollback also failed "
                f"({rollback_exc}) — manual repair needed"
            )
        return f"opens save failed after facts write; facts rolled back: {exc}"
    return None


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
                "ref": [str(r) for r in (entry.get("origin_ref") or ["fact-production"])],
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


def cmd_update(args: argparse.Namespace) -> int:
    """Patch an existing fact by F-n (replaces G3 update-decision write path)."""
    if not args.confirm:
        return _fail("update requires --confirm (human confirm gate)")
    fact_id = str(args.id or "").strip()
    if not fact_id:
        return _fail("update requires --id (F-n)")
    if not fact_id.startswith("F-"):
        return _fail(f"update id must be F-n, got {fact_id!r}")
    text = str(args.text or "").strip()
    if not text:
        return _fail("update requires non-empty --text")

    slice_dir = _slice(args.revision_dir)
    path = facts_path(slice_dir)
    if not path.is_file():
        return _fail(f"facts not found: {path}")
    facts = load_facts(path)
    fact = next((f for f in facts if isinstance(f, dict) and f.get("id") == fact_id), None)
    if fact is None:
        return _fail(f"fact not found: {fact_id!r}")
    fact["text"] = text
    try:
        save_facts(path, facts, allowed_lenses=_allowed_lenses(slice_dir) or None)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(
        {
            "ok": True,
            "command": "update",
            "updated": fact_id,
            "fact": fact,
            "stale_signal": True,
            "suggest_check": True,
            "message": "fact updated; collab arc may be stale — suggest check / optional regenerate",
        }
    )


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete one fact without renumbering any surviving stable IDs."""
    if not args.confirm:
        return _fail("delete requires --confirm (human confirm gate)")
    fact_id = str(args.id or "").strip()
    if not fact_id:
        return _fail("delete requires --id (F-n)")

    slice_dir = _slice(args.revision_dir)
    path = facts_path(slice_dir)
    if not path.is_file():
        return _fail(f"facts not found: {path}")
    facts = load_facts(path)
    deleted = next(
        (fact for fact in facts if isinstance(fact, dict) and fact.get("id") == fact_id),
        None,
    )
    if deleted is None:
        return _fail(f"fact not found: {fact_id!r}")
    remaining = [fact for fact in facts if fact is not deleted]

    try:
        if remaining:
            save_facts(
                path,
                remaining,
                allowed_lenses=_allowed_lenses(slice_dir) or None,
            )
        else:
            path.unlink()
    except (OSError, ValueError) as exc:
        return _fail(str(exc))

    return _ok(
        {
            "ok": True,
            "command": "delete",
            "deleted": fact_id,
            "facts_total": len(remaining),
            "stale_signal": True,
            "suggest_check": True,
            "message": (
                "fact deleted without renumbering; collab and Formal arcs may "
                "reference it — suggest check / optional regenerate"
            ),
        }
    )


def cmd_settle_open(args: argparse.Namespace) -> int:
    """Settle open → 1:N facts (origin.type=discovered); atomic with open status."""
    if not bool(getattr(args, "confirm", False)):
        return _fail(
            "settle-open requires --confirm (archive-10.0 T2 human confirm gate)"
        )
    slice_dir = _slice(args.revision_dir)
    opens = load_opens(opens_path(slice_dir))
    open_item = _find_open(opens, args.open_id)
    if open_item is None:
        return _fail(f"open not found: {args.open_id!r}")
    if open_item.get("status") != "open":
        return _fail(
            f"open {args.open_id!r} is not status=open (got {open_item.get('status')!r})"
        )

    facts_file = Path(args.facts_file)
    if not facts_file.is_file():
        return _fail(f"facts-file not found: {facts_file}")
    try:
        entries = json.loads(facts_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail(f"invalid facts-file JSON: {exc}")
    if not isinstance(entries, list) or not entries:
        return _fail("--facts-file must be a non-empty JSON array")

    fpath = facts_path(slice_dir)
    facts_before = load_facts(fpath) if fpath.is_file() else []
    facts = copy.deepcopy(facts_before)
    fact_ids: list[str] = []
    undeclared: list[dict[str, Any]] = []
    n = _next_fact_id(facts)
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            return _fail(f"facts-file[{i}] must be an object")
        text = str(entry.get("text") or "").strip()
        if not text:
            return _fail(f"facts-file[{i}]: text required")
        tags_raw = entry.get("lens_tags")
        if not isinstance(tags_raw, list):
            return _fail(f"facts-file[{i}]: lens_tags must be an array")
        lens_tags = [str(t).strip().upper() for t in tags_raw if str(t).strip()]
        if not lens_tags:
            return _fail(f"facts-file[{i}]: lens_tags must be non-empty")
        fact_id = f"F-{n}"
        fact: dict[str, Any] = {
            "id": fact_id,
            "text": text,
            "lens_tags": lens_tags,
            "origin": {"type": "discovered", "ref": [args.open_id]},
        }
        declared = entry.get("anchors")
        if declared is not None:
            fact["anchors"] = declared
        else:
            undeclared.append(fact)
        facts.append(fact)
        fact_ids.append(fact_id)
        n += 1

    code_refs = [
        str(r).strip() for r in (open_item.get("code_refs") or []) if str(r).strip()
    ]
    if undeclared and code_refs:
        _distribute_code_refs(undeclared, code_refs)

    open_item["status"] = "settled"
    open_item["resolved_by"] = fact_ids

    err = _commit_facts_then_opens(
        slice_dir,
        facts_before=facts_before,
        facts_after=facts,
        opens_after=opens,
    )
    if err:
        return _fail(err)
    return _ok(
        {
            "ok": True,
            "command": "settle-open",
            "fact_ids": fact_ids,
            "settled": args.open_id,
            "stale_signal": True,
            "suggest_check": True,
            "message": (
                "facts committed via settle-open; collab arc may be stale — "
                "suggest check / optional regenerate"
            ),
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

    p = sub.add_parser(
        "settle-open",
        help="Open→1:N facts + open settled (atomic; requires --confirm)",
    )
    p.add_argument("--revision-dir", required=True)
    p.add_argument("--open-id", required=True)
    p.add_argument("--facts-file", required=True)
    p.add_argument(
        "--confirm",
        action="store_true",
        help="Required; mechanical gate for human confirm",
    )
    p.set_defaults(func=cmd_settle_open)

    p = sub.add_parser("update", help="Patch fact text by F-n (requires --confirm)")
    p.add_argument("--revision-dir", required=True)
    p.add_argument("--id", required=True, help="Fact id F-n")
    p.add_argument("--text", required=True)
    p.add_argument(
        "--confirm",
        action="store_true",
        help="Required; mechanical gate for human confirm",
    )
    p.set_defaults(func=cmd_update)

    p = sub.add_parser(
        "delete",
        help="Delete one fact without renumbering surviving IDs (requires --confirm)",
    )
    p.add_argument("--revision-dir", required=True)
    p.add_argument("--id", required=True, help="Fact id F-n")
    p.add_argument(
        "--confirm",
        action="store_true",
        help="Required; mechanical gate for human confirm",
    )
    p.set_defaults(func=cmd_delete)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
