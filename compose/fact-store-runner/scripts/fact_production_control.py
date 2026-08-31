#!/usr/bin/env python3
"""Permit-gated fact-production control (archive-13.0).

All G2/G3 fact mutations use ``propose`` → ``ack`` → ``consume``. A proposal
persists its exact normalized payload and digest before a human ACK; consume
accepts only the acknowledged permit ID and its stable slice key. The control
serializes facts/opens mutations, records an interrupted write as ``consuming``,
and reconciles exact snapshots before any retry.

Subcommands: propose · ack · consume · revoke · reconcile

CLI: ``python3 fact_production_control.py --help``

Process how: docs/domain/archive/compose/archive-11.0/
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import secrets
import sys
from pathlib import Path
from typing import Any

_RUNNER_SCRIPTS = Path(__file__).resolve().parent
_COMPOSE = _RUNNER_SCRIPTS.parents[1]
_SCRIPTS = _COMPOSE / "scripts"
_INDUCTIVE = _SCRIPTS / "inductive"
_INDUCTIVE_SCHEMA = _INDUCTIVE / "schema"
for _p in (_SCRIPTS, _INDUCTIVE, _INDUCTIVE_SCHEMA, _RUNNER_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from l_ledger_schema import active_slice_dir  # noqa: E402
from facts_schema import (  # noqa: E402
    facts_path,
    load_facts,
    save_facts,
    validate_facts,
)
from opens_schema import load_opens, opens_path, save_opens, validate_opens  # noqa: E402
from open_point_store import (  # noqa: E402
    apply_loop_after,
    assert_slice_writable,
    lens_snapshot,
    load_bundle,
    preview_settle,
    registry_lens_keys,
)
from open_point_batch_schema import (  # noqa: E402
    load_open_point_batches,
    open_point_batches_path,
)
from open_point_state_schema import (  # noqa: E402
    load_open_point_state,
    open_point_state_path,
)
from compose_state_lock import (  # noqa: E402
    canonical_digest,
    compose_state_lock,
    durable_unlink,
    exclusive_lock,
)
from fact_production_permit_schema import (  # noqa: E402
    digest_payload,
    load_permit_store,
    permit_lock_path,
    save_permit_store,
)


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


def _allowed_lenses(
    slice_dir: Path, project_root: Path | str | None = None
) -> list[str]:
    return registry_lens_keys(lens_snapshot(slice_dir, project_root))


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


def _save_facts_inductive(
    slice_dir: Path,
    facts: list[dict[str, Any]],
    project_root: Path | str | None = None,
) -> None:
    save_facts(
        facts_path(slice_dir),
        facts,
        allowed_lenses=_allowed_lenses(slice_dir, project_root) or None,
    )


def _commit_facts_then_opens(
    slice_dir: Path,
    *,
    facts_before: list[dict[str, Any]],
    facts_after: list[dict[str, Any]],
    opens_after: list[dict[str, Any]],
    project_root: Path | str | None = None,
) -> str | None:
    """Validate both stores, write facts then opens; roll back facts if opens fails.

    Returns error message or None on success.
    """
    allowed = _allowed_lenses(slice_dir, project_root)
    ferrs = validate_facts(facts_after, allowed_lenses=allowed or None)
    if ferrs:
        return "; ".join(ferrs)
    oerrs = validate_opens(opens_after)
    if oerrs:
        return "; ".join(oerrs)

    try:
        _save_facts_inductive(slice_dir, facts_after, project_root)
    except (ValueError, OSError) as exc:
        return str(exc)

    try:
        save_opens(opens_path(slice_dir), opens_after)
    except (ValueError, OSError) as exc:
        try:
            fpath = facts_path(slice_dir)
            if facts_before:
                _save_facts_inductive(slice_dir, facts_before, project_root)
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
    del args
    return _fail("commit is retired; use propose --kind append → ack → consume")
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
            "message": "facts committed; collab arc may be stale — suggest check / optional semantic rebuild",
        }
    )


def cmd_cancel(args: argparse.Namespace) -> int:
    del args
    return _fail("cancel is retired; use revoke --permit-id … --slice-key …")
    return _ok(
        {
            "ok": True,
            "command": "cancel",
            "written": False,
            "message": "whole batch cancelled; _facts.json unchanged",
        }
    )


def cmd_update(args: argparse.Namespace) -> int:
    del args
    return _fail("update is retired; use propose --kind update → ack → consume")


def cmd_delete(args: argparse.Namespace) -> int:
    del args
    return _fail("delete is retired; use propose --kind delete → ack → consume")


def cmd_settle_open(args: argparse.Namespace) -> int:
    """Settle open → 1:N facts (origin.type=discovered); atomic with open status."""
    del args
    return _fail("settle-open is retired; use propose --kind settle_open → ack → consume")
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
                "suggest check / optional semantic rebuild"
            ),
        }
    )


def _slice_context(
    revision_dir: str,
    slice_key: str | None = None,
) -> tuple[Path, Path, str]:
    root = Path(revision_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"revision-dir not found: {root}")
    if slice_key is None:
        slice_dir = active_slice_dir(root)
        try:
            key = str(slice_dir.relative_to(root)) or "."
        except ValueError as exc:
            raise ValueError("active slice is outside revision-dir") from exc
        return root, slice_dir, key

    raw = str(slice_key).strip()
    if not raw:
        raise ValueError("slice-key must be non-empty")
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("slice-key must be a relative path below revision-dir")
    slice_dir = (root / candidate).resolve()
    try:
        slice_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError("slice-key escapes revision-dir") from exc
    if not slice_dir.is_dir():
        raise ValueError(f"slice-key not found: {raw!r}")
    return root, slice_dir, str(slice_dir.relative_to(root)) or "."


def _load_facts_optional(slice_dir: Path) -> tuple[list[dict[str, Any]], bool]:
    path = facts_path(slice_dir)
    return (load_facts(path), True) if path.is_file() else ([], False)


def _load_opens_optional(slice_dir: Path) -> tuple[list[dict[str, Any]], bool]:
    path = opens_path(slice_dir)
    return (load_opens(path), True) if path.is_file() else ([], False)


def _load_state_optional(slice_dir: Path) -> tuple[dict[str, Any], bool]:
    path = open_point_state_path(slice_dir)
    return load_open_point_state(path), path.is_file()


def _load_batches_optional(slice_dir: Path) -> tuple[dict[str, Any], bool]:
    path = open_point_batches_path(slice_dir)
    return load_open_point_batches(path), path.is_file()


def _entry_facts(
    entries: list[dict[str, Any]],
    *,
    facts_before: list[dict[str, Any]],
    origin_ref: list[str],
    slice_dir: Path,
    project_root: Path | str | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    facts = copy.deepcopy(facts_before)
    fact_ids: list[str] = []
    undeclared: list[dict[str, Any]] = []
    next_id = _next_fact_id(facts)
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"facts[{index}] must be an object")
        text = str(entry.get("text") or "").strip()
        if not text:
            raise ValueError(f"facts[{index}]: text required")
        tags_raw = entry.get("lens_tags")
        if not isinstance(tags_raw, list):
            raise ValueError(f"facts[{index}]: lens_tags must be an array")
        lens_tags = [str(tag).strip().upper() for tag in tags_raw if str(tag).strip()]
        if not lens_tags:
            raise ValueError(f"facts[{index}]: lens_tags must be non-empty")
        fact: dict[str, Any] = {
            "id": f"F-{next_id}",
            "text": text,
            "lens_tags": lens_tags,
            "origin": {"type": "discovered", "ref": origin_ref},
        }
        if entry.get("anchors") is not None:
            fact["anchors"] = entry["anchors"]
        else:
            undeclared.append(fact)
        facts.append(fact)
        fact_ids.append(fact["id"])
        next_id += 1
    errors = validate_facts(
        facts, allowed_lenses=_allowed_lenses(slice_dir, project_root) or None
    )
    if errors:
        raise ValueError("; ".join(errors))
    return facts, fact_ids, undeclared


def _build_proposal(
    args: argparse.Namespace,
    slice_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    facts_before, facts_before_exists = _load_facts_optional(slice_dir)
    opens_before: list[dict[str, Any]] | None = None
    opens_before_exists: bool | None = None
    kind = str(args.kind)
    project_root = getattr(args, "project_root", None) or None

    if kind == "append":
        entries = _load_entries(args)
        facts_after, fact_ids, _ = _entry_facts(
            entries,
            facts_before=facts_before,
            origin_ref=["fact-production"],
            slice_dir=slice_dir,
            project_root=project_root,
        )
        payload = {
            "kind": kind,
            "facts_after": facts_after,
            "facts_file_exists_after": True,
            "opens_after": None,
            "fact_ids": fact_ids,
        }
        preview = {"kind": kind, "facts_after": facts_after, "fact_ids": fact_ids}
    elif kind == "update":
        fact_id = str(args.id or "").strip()
        text = str(args.text or "").strip()
        if not fact_id or not text:
            raise ValueError("update proposal requires --id F-n and non-empty --text")
        facts_after = copy.deepcopy(facts_before)
        fact = next((item for item in facts_after if item.get("id") == fact_id), None)
        if fact is None:
            raise ValueError(f"fact not found: {fact_id!r}")
        before = copy.deepcopy(fact)
        fact["text"] = text
        errors = validate_facts(
            facts_after,
            allowed_lenses=_allowed_lenses(slice_dir, project_root) or None,
        )
        if errors:
            raise ValueError("; ".join(errors))
        payload = {
            "kind": kind,
            "facts_after": facts_after,
            "facts_file_exists_after": True,
            "opens_after": None,
            "updated": fact_id,
        }
        preview = {"kind": kind, "before": before, "after": fact, "updated": fact_id}
    elif kind == "delete":
        fact_id = str(args.id or "").strip()
        if not fact_id:
            raise ValueError("delete proposal requires --id F-n")
        deleted = next((item for item in facts_before if item.get("id") == fact_id), None)
        if deleted is None:
            raise ValueError(f"fact not found: {fact_id!r}")
        facts_after = [item for item in facts_before if item.get("id") != fact_id]
        payload = {
            "kind": kind,
            "facts_after": facts_after,
            "facts_file_exists_after": bool(facts_after),
            "opens_after": None,
            "deleted": fact_id,
        }
        preview = {"kind": kind, "deleted": deleted, "facts_after": facts_after}
    elif kind == "settle_open":
        open_id = str(args.open_id or "").strip()
        if not open_id:
            raise ValueError("settle_open proposal requires --open-id")
        bundle = load_bundle(slice_dir)
        opens_before = bundle["opens"]
        opens_before_exists = opens_path(slice_dir).is_file()
        state_before = bundle["state"]
        state_before_exists = open_point_state_path(slice_dir).is_file()
        batches_before = bundle["batches"]
        batches_before_exists = open_point_batches_path(slice_dir).is_file()
        if (
            state_before.get("phase") != "processing"
            or state_before.get("active_open_id") != open_id
        ):
            raise ValueError(f"open {open_id!r} is not the active open")
        open_before = _find_open(opens_before, open_id)
        if open_before is None:
            raise ValueError(f"open not found: {open_id!r}")
        if open_before.get("status") != "open":
            raise ValueError(f"open {open_id!r} is not status=open")
        entries = _load_entries(args)
        facts_after, fact_ids, undeclared = _entry_facts(
            entries,
            facts_before=facts_before,
            origin_ref=[open_id],
            slice_dir=slice_dir,
            project_root=project_root,
        )
        _distribute_code_refs(
            undeclared,
            [str(ref).strip() for ref in (open_before.get("code_refs") or []) if str(ref).strip()],
        )
        previewed = preview_settle(slice_dir, open_id, fact_ids)
        opens_after = previewed["opens"]
        state_after = previewed["state"]
        batches_after = previewed["batches"]
        errors = validate_opens(opens_after)
        if errors:
            raise ValueError("; ".join(errors))
        open_after = _find_open(opens_after, open_id)
        payload = {
            "kind": kind,
            "facts_after": facts_after,
            "facts_file_exists_after": True,
            "opens_after": opens_after,
            "opens_file_exists_after": True,
            "state_after": state_after,
            "state_file_exists_after": True,
            "batches_after": batches_after,
            "batches_file_exists_after": True,
            "settled": open_id,
            "fact_ids": fact_ids,
        }
        preview = {
            "kind": kind,
            "open_before": open_before,
            "open_after": open_after,
            "facts_after": facts_after,
            "fact_ids": fact_ids,
        }
    else:
        raise ValueError(f"unsupported proposal kind: {kind!r}")

    precondition = {
        "facts_digest": canonical_digest(facts_before),
        "facts_file_exists": facts_before_exists,
        "opens_digest": canonical_digest(opens_before) if opens_before is not None else None,
        "opens_file_exists": opens_before_exists,
    }
    snapshot = {
        "facts_before": facts_before,
        "facts_file_exists_before": facts_before_exists,
        "opens_before": opens_before,
        "opens_file_exists_before": opens_before_exists,
    }
    if kind == "settle_open":
        precondition.update(
            {
                "state_digest": canonical_digest(state_before),
                "state_file_exists": state_before_exists,
                "batches_digest": canonical_digest(batches_before),
                "batches_file_exists": batches_before_exists,
            }
        )
        snapshot.update(
            {
                "state_before": state_before,
                "state_file_exists_before": state_before_exists,
                "batches_before": batches_before,
                "batches_file_exists_before": batches_before_exists,
            }
        )
    return payload, precondition, {"snapshot": snapshot, "preview": preview}


def _find_permit(store: dict[str, Any], permit_id: str) -> dict[str, Any] | None:
    return next((item for item in store["permits"] if item.get("id") == permit_id), None)


def _active_permit(store: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in store["permits"]
            if item.get("state") in {"proposed", "acknowledged", "consuming", "repair_required"}
        ),
        None,
    )


def _matches_snapshot(
    slice_dir: Path,
    *,
    facts: list[dict[str, Any]],
    facts_exists: bool,
    opens: list[dict[str, Any]] | None,
    opens_exists: bool | None,
    state: dict[str, Any] | None = None,
    state_exists: bool | None = None,
    batches: dict[str, Any] | None = None,
    batches_exists: bool | None = None,
) -> bool:
    current_facts, current_facts_exists = _load_facts_optional(slice_dir)
    if current_facts_exists != facts_exists or current_facts != facts:
        return False
    if opens is None:
        return True
    current_opens, current_opens_exists = _load_opens_optional(slice_dir)
    if current_opens_exists != opens_exists or current_opens != opens:
        return False
    if state is None and batches is None:
        return True
    if state is not None:
        current_state, current_state_exists = _load_state_optional(slice_dir)
        if current_state_exists != bool(state_exists) or current_state != state:
            return False
    if batches is not None:
        current_batches, current_batches_exists = _load_batches_optional(slice_dir)
        if current_batches_exists != bool(batches_exists) or current_batches != batches:
            return False
    return True


def _write_facts_exact(
    slice_dir: Path,
    facts: list[dict[str, Any]],
    *,
    exists_after: bool,
    project_root: Path | str | None = None,
) -> None:
    path = facts_path(slice_dir)
    if not exists_after:
        if path.is_file():
            durable_unlink(path)
        return
    _save_facts_inductive(slice_dir, facts, project_root)


def _reconcile_permit(slice_dir: Path, store: dict[str, Any], permit: dict[str, Any]) -> str:
    """Return consumed, acknowledged, or repair_required after exact comparison."""
    snapshot = permit["snapshot"]
    payload = permit["payload"]
    before_matches = _matches_snapshot(
        slice_dir,
        facts=snapshot["facts_before"],
        facts_exists=bool(snapshot["facts_file_exists_before"]),
        opens=snapshot["opens_before"],
        opens_exists=snapshot["opens_file_exists_before"],
        state=snapshot.get("state_before"),
        state_exists=snapshot.get("state_file_exists_before"),
        batches=snapshot.get("batches_before"),
        batches_exists=snapshot.get("batches_file_exists_before"),
    )
    after_matches = _matches_snapshot(
        slice_dir,
        facts=payload["facts_after"],
        facts_exists=bool(payload["facts_file_exists_after"]),
        opens=payload["opens_after"],
        opens_exists=payload.get("opens_file_exists_after"),
        state=payload.get("state_after"),
        state_exists=payload.get("state_file_exists_after"),
        batches=payload.get("batches_after"),
        batches_exists=payload.get("batches_file_exists_after"),
    )
    if after_matches:
        permit["state"] = "consumed"
        save_permit_store(slice_dir, store)
        return "consumed"
    if before_matches:
        permit["state"] = "acknowledged"
        save_permit_store(slice_dir, store)
        return "acknowledged"

    permit["state"] = "repair_required"
    save_permit_store(slice_dir, store)
    return "repair_required"


def cmd_propose(args: argparse.Namespace) -> int:
    try:
        _, slice_dir, slice_key = _slice_context(args.revision_dir)
        with exclusive_lock(permit_lock_path(slice_dir)):
            with compose_state_lock(slice_dir):
                store = load_permit_store(slice_dir)
                active = _active_permit(store)
                if active is not None:
                    return _fail(
                        f"active permit {active['id']!r} is {active['state']!r}; "
                        "consume, revoke, or recover it first"
                    )
                payload, precondition, detail = _build_proposal(args, slice_dir)
                permit = {
                    "id": f"p_{secrets.token_urlsafe(24)}",
                    "state": "proposed",
                    "kind": payload["kind"],
                    "slice_key": slice_key,
                    "digest_version": "v1",
                    "digest": digest_payload(payload),
                    "payload": payload,
                    "precondition": precondition,
                    "snapshot": detail["snapshot"],
                }
                store["permits"].append(permit)
                save_permit_store(slice_dir, store)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _fail(str(exc))
    return _ok(
        {
            "ok": True,
            "command": "propose",
            "permit_id": permit["id"],
            "slice_key": slice_key,
            "digest": permit["digest"],
            "digest_version": "v1",
            "preview": detail["preview"],
        }
    )


def cmd_ack(args: argparse.Namespace) -> int:
    try:
        _, slice_dir, slice_key = _slice_context(args.revision_dir, args.slice_key)
        with exclusive_lock(permit_lock_path(slice_dir)):
            store = load_permit_store(slice_dir)
            permit = _find_permit(store, args.permit_id)
            if permit is None:
                return _fail(f"permit not found: {args.permit_id!r}")
            if permit["slice_key"] != slice_key:
                return _fail("permit slice-key mismatch")
            if permit["state"] != "proposed":
                return _fail(f"permit is not proposed: {permit['state']!r}")
            if not args.human_ack:
                return _fail("ack requires --human-ack")
            if args.digest != permit["digest"]:
                return _fail("ack digest does not match the proposed payload")
            permit["state"] = "acknowledged"
            save_permit_store(slice_dir, store)
    except (OSError, ValueError) as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "command": "ack", "permit_id": args.permit_id, "acknowledged": True})


def cmd_consume(args: argparse.Namespace) -> int:
    project_root = getattr(args, "project_root", None) or None
    try:
        _, slice_dir, slice_key = _slice_context(args.revision_dir, args.slice_key)
        with exclusive_lock(permit_lock_path(slice_dir)):
            with compose_state_lock(slice_dir):
                store = load_permit_store(slice_dir)
                permit = _find_permit(store, args.permit_id)
                if permit is None:
                    return _fail(f"permit not found: {args.permit_id!r}")
                if permit["slice_key"] != slice_key:
                    return _fail("permit slice-key mismatch")
                if permit["state"] == "consuming":
                    state = _reconcile_permit(slice_dir, store, permit)
                    return _fail(f"permit reconciliation completed as {state!r}; retry if acknowledged")
                if permit["state"] != "acknowledged":
                    return _fail(f"permit is not acknowledged: {permit['state']!r}")
                precondition = permit["precondition"]
                current_facts, current_facts_exists = _load_facts_optional(slice_dir)
                if (
                    current_facts_exists != precondition["facts_file_exists"]
                    or canonical_digest(current_facts) != precondition["facts_digest"]
                ):
                    return _fail("facts baseline changed; propose again")
                if precondition["opens_digest"] is not None:
                    current_opens, current_opens_exists = _load_opens_optional(slice_dir)
                    if (
                        current_opens_exists != precondition["opens_file_exists"]
                        or canonical_digest(current_opens) != precondition["opens_digest"]
                    ):
                        return _fail("opens baseline changed; propose again")
                if precondition.get("state_digest") is not None:
                    current_state, current_state_exists = _load_state_optional(slice_dir)
                    if (
                        current_state_exists != precondition["state_file_exists"]
                        or canonical_digest(current_state) != precondition["state_digest"]
                    ):
                        return _fail("state baseline changed; propose again")
                if precondition.get("batches_digest") is not None:
                    current_batches, current_batches_exists = _load_batches_optional(
                        slice_dir
                    )
                    if (
                        current_batches_exists != precondition["batches_file_exists"]
                        or canonical_digest(current_batches)
                        != precondition["batches_digest"]
                    ):
                        return _fail("batches baseline changed; propose again")

                permit["state"] = "consuming"
                save_permit_store(slice_dir, store)
                payload = permit["payload"]
                try:
                    if payload["kind"] == "settle_open":
                        assert_slice_writable(slice_dir)
                    _write_facts_exact(
                        slice_dir,
                        payload["facts_after"],
                        exists_after=bool(payload["facts_file_exists_after"]),
                        project_root=project_root,
                    )
                    if payload["kind"] == "settle_open":
                        apply_loop_after(
                            slice_dir,
                            opens=payload["opens_after"],
                            state=payload["state_after"],
                            batches=payload["batches_after"],
                            operation="settle-open",
                        )
                    elif payload["opens_after"] is not None:
                        save_opens(opens_path(slice_dir), payload["opens_after"])
                    permit["state"] = "consumed"
                    permit["receipt"] = {
                        "fact_ids": payload.get("fact_ids", []),
                        "kind": payload["kind"],
                    }
                    save_permit_store(slice_dir, store)
                except (OSError, ValueError) as exc:
                    if payload.get("kind") == "settle_open":
                        snapshot = permit["snapshot"]
                        try:
                            _write_facts_exact(
                                slice_dir,
                                snapshot["facts_before"],
                                exists_after=bool(
                                    snapshot["facts_file_exists_before"]
                                ),
                                project_root=project_root,
                            )
                        except (OSError, ValueError):
                            pass
                    state = _reconcile_permit(slice_dir, store, permit)
                    return _fail(f"consume interrupted ({exc}); reconciled as {state!r}")
    except (OSError, ValueError) as exc:
        return _fail(str(exc))

    payload = permit["payload"]
    result: dict[str, Any] = {
        "ok": True,
        "command": "consume",
        "permit_id": args.permit_id,
        "kind": payload["kind"],
        "stale_signal": True,
        "suggest_check": True,
    }
    for key in ("fact_ids", "updated", "deleted", "settled"):
        if key in payload:
            result[key] = payload[key]
    result["facts_total"] = len(payload["facts_after"])
    return _ok(result)


def cmd_revoke(args: argparse.Namespace) -> int:
    try:
        _, slice_dir, slice_key = _slice_context(args.revision_dir, args.slice_key)
        with exclusive_lock(permit_lock_path(slice_dir)):
            store = load_permit_store(slice_dir)
            permit = _find_permit(store, args.permit_id)
            if permit is None or permit["slice_key"] != slice_key:
                return _fail("permit not found in slice")
            if permit["state"] not in {"proposed", "acknowledged"}:
                return _fail(f"permit cannot be revoked from {permit['state']!r}")
            permit["state"] = "revoked"
            save_permit_store(slice_dir, store)
    except (OSError, ValueError) as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "command": "revoke", "permit_id": args.permit_id, "written": False})


def cmd_reconcile(args: argparse.Namespace) -> int:
    try:
        _, slice_dir, slice_key = _slice_context(args.revision_dir, args.slice_key)
        with exclusive_lock(permit_lock_path(slice_dir)):
            with compose_state_lock(slice_dir):
                store = load_permit_store(slice_dir)
                permit = _find_permit(store, args.permit_id)
                if permit is None or permit["slice_key"] != slice_key:
                    return _fail("permit not found in slice")
                if permit["state"] != "consuming":
                    return _fail(f"permit is not consuming: {permit['state']!r}")
                state = _reconcile_permit(slice_dir, store, permit)
    except (OSError, ValueError) as exc:
        return _fail(str(exc))
    return _ok({"ok": state != "repair_required", "command": "reconcile", "state": state})


def cmd_recover(args: argparse.Namespace) -> int:
    if not args.human_ack:
        return _fail("recover requires --human-ack")
    try:
        _, slice_dir, slice_key = _slice_context(args.revision_dir, args.slice_key)
        with exclusive_lock(permit_lock_path(slice_dir)):
            with compose_state_lock(slice_dir):
                store = load_permit_store(slice_dir)
                permit = _find_permit(store, args.permit_id)
                if permit is None or permit["slice_key"] != slice_key:
                    return _fail("permit not found in slice")
                if permit["state"] != "repair_required":
                    return _fail(f"permit is not repair_required: {permit['state']!r}")
                snapshot = permit["snapshot"]
                payload = permit["payload"]
                if args.resolution == "restore_before":
                    facts, facts_exists = (
                        snapshot["facts_before"],
                        bool(snapshot["facts_file_exists_before"]),
                    )
                    opens, opens_exists = (
                        snapshot["opens_before"],
                        snapshot["opens_file_exists_before"],
                    )
                    state, state_exists = (
                        snapshot.get("state_before"),
                        snapshot.get("state_file_exists_before"),
                    )
                    batches, batches_exists = (
                        snapshot.get("batches_before"),
                        snapshot.get("batches_file_exists_before"),
                    )
                else:
                    facts, facts_exists = (
                        payload["facts_after"],
                        bool(payload["facts_file_exists_after"]),
                    )
                    opens, opens_exists = (
                        payload["opens_after"],
                        payload.get("opens_file_exists_after"),
                    )
                    state, state_exists = (
                        payload.get("state_after"),
                        payload.get("state_file_exists_after"),
                    )
                    batches, batches_exists = (
                        payload.get("batches_after"),
                        payload.get("batches_file_exists_after"),
                    )
                _write_facts_exact(
                    slice_dir,
                    facts,
                    exists_after=facts_exists,
                    project_root=getattr(args, "project_root", None) or None,
                )
                if payload.get("kind") == "settle_open":
                    apply_loop_after(
                        slice_dir,
                        opens=opens,
                        state=state,
                        batches=batches,
                        operation="recover",
                    )
                elif opens is not None:
                    if opens_exists:
                        save_opens(opens_path(slice_dir), opens)
                    elif opens_path(slice_dir).is_file():
                        durable_unlink(opens_path(slice_dir))
                if not _matches_snapshot(
                    slice_dir,
                    facts=facts,
                    facts_exists=facts_exists,
                    opens=opens,
                    opens_exists=opens_exists,
                    state=state,
                    state_exists=state_exists,
                    batches=batches,
                    batches_exists=batches_exists,
                ):
                    return _fail("recover did not reach the requested exact state")
                permit["state"] = (
                    "acknowledged"
                    if args.resolution == "restore_before"
                    else "consumed"
                )
                save_permit_store(slice_dir, store)
    except (OSError, ValueError) as exc:
        return _fail(str(exc))
    return _ok(
        {
            "ok": True,
            "command": "recover",
            "permit_id": args.permit_id,
            "state": permit["state"],
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        default="",
        help="Session root so section-registry loads from the SKILL install",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("propose", help="Persist an exact fact mutation preview")
    p.add_argument("--revision-dir", required=True)
    p.add_argument(
        "--kind",
        required=True,
        choices=("append", "settle_open", "update", "delete"),
    )
    p.add_argument("--facts-json", default=None, help="Candidate facts JSON or stdin")
    p.add_argument("--open-id", default=None)
    p.add_argument("--id", default=None, help="Fact id F-n for update/delete")
    p.add_argument("--text", default=None, help="Replacement fact text for update")
    p.set_defaults(func=cmd_propose)

    p = sub.add_parser("ack", help="Record a human ACK for one displayed preview")
    p.add_argument("--revision-dir", required=True)
    p.add_argument("--permit-id", required=True)
    p.add_argument("--slice-key", required=True)
    p.add_argument("--digest", required=True)
    p.add_argument("--human-ack", action="store_true")
    p.set_defaults(func=cmd_ack)

    p = sub.add_parser("consume", help="Consume one acknowledged permit")
    p.add_argument("--revision-dir", required=True)
    p.add_argument("--permit-id", required=True)
    p.add_argument("--slice-key", required=True)
    p.set_defaults(func=cmd_consume)

    p = sub.add_parser("revoke", help="Revoke a proposed or acknowledged permit")
    p.add_argument("--revision-dir", required=True)
    p.add_argument("--permit-id", required=True)
    p.add_argument("--slice-key", required=True)
    p.set_defaults(func=cmd_revoke)

    p = sub.add_parser("reconcile", help="Recover an interrupted consuming permit")
    p.add_argument("--revision-dir", required=True)
    p.add_argument("--permit-id", required=True)
    p.add_argument("--slice-key", required=True)
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("recover", help="Resolve a repair-required permit exactly")
    p.add_argument("--revision-dir", required=True)
    p.add_argument("--permit-id", required=True)
    p.add_argument("--slice-key", required=True)
    p.add_argument(
        "--resolution",
        required=True,
        choices=("restore_before", "write_after"),
    )
    p.add_argument("--human-ack", action="store_true")
    p.set_defaults(func=cmd_recover)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
