#!/usr/bin/env python3
"""CLI for deductive-runner confirm-gate + quarantine-unref listing.

Subcommands:
    pending-init       Ensure pending store exists
    pending-add        Add an open pending item
    pending-replace    Replace open edge_hole items from a leftover list
    pending-resolve    Resolve an open item (resolved|escalated|out_of_scope)
    pending-list       List pending items (default: open only)
    quarantine-unref   List quarantined facts not cited by any other fact
    gate-check         Fail if facts or pending store is missing
    disposition-patch-validate  Validate post-intake retag op-list patch
    disposition-patch-apply     Apply post-intake retag op-list patch to _facts.json
    consume-policy-check        Fail if role lacks non-empty consume_policy.rules

Intake Disposition Confirm uses fact-intake disposition control
(fact-intake-disposition-review.patch), not these subcommands.

Design rationale (source repo, why-only):
docs/domain/archive/compose/archive-3.0/compose-deductive-runner-architecture-design.md §4.5;
docs/domain/archive/compose/archive-6.0/compose-plan-deductive-consume-disposition-design.md;
docs/domain/archive/compose/archive-45.0/compose-floor-edge-hole-pending-replace-design.md;
docs/domain/archive/compose/archive-47.0/compose-cascade-only-exit-edge-hole-ledger-design.md;
docs/domain/archive/compose/archive-48.0/compose-pending-confirm-display-only-design.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_DEDUCTIVE = Path(__file__).resolve().parent
_SCRIPTS = _DEDUCTIVE.parent
_KERNEL = _SCRIPTS / "_kernel"
for p in (_SCRIPTS, _KERNEL, _DEDUCTIVE):
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
    save_facts,
    unlensed_fact_ids,
)
from compose_state_lock import compose_state_lock  # noqa: E402
from l_ledger_schema import active_slice_dir  # noqa: E402
from derive_shell import collect_ref_tokens  # noqa: E402
from deductive_disposition_patch import (  # noqa: E402
    apply_disposition_patch,
    disposition_counts,
    validate_disposition_patch,
)
from load_compose_template import (  # noqa: E402
    ComposeTemplateLoadError,
    load_compose_template,
)
from section_registry_schema import fetch_section_registry, lens_key_sequence  # noqa: E402
from workflow_paths import resolve_revision_runtime_profile  # noqa: E402

_SCOPE = _SCRIPTS / "schema" / "section" / "scope"
if str(_SCOPE) not in sys.path:
    sys.path.insert(0, str(_SCOPE))
from role_instance_schema import validate_role_instance  # noqa: E402


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _runtime_profile(args: argparse.Namespace):
    return resolve_revision_runtime_profile(
        Path(args.revision_dir),
        Path(args.project_root).resolve(),
    )


def _slice_dir(args: argparse.Namespace) -> Path:
    return active_slice_dir(args.revision_dir.resolve())


def cmd_pending_init(args: argparse.Namespace) -> int:
    path = pending_path(_slice_dir(args))
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
    path = pending_path(_slice_dir(args))
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


def _parse_replace_items(raw: str) -> list[dict[str, Any]] | str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return f"items-json invalid: {exc}"
    if not isinstance(data, list):
        return "items-json must be an array"
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            return f"items-json[{i}] must be an object"
        lens = str(item.get("lens", "")).strip().upper()
        if not lens:
            return f"items-json[{i}].lens must be a non-empty string"
        if lens in seen:
            return f"items-json duplicate lens {lens}"
        seen.add(lens)
        uncovered = item.get("uncovered")
        if not isinstance(uncovered, list) or not uncovered:
            return f"items-json[{i}].uncovered must be a non-empty array"
        ids: list[str] = []
        for j, uid in enumerate(uncovered):
            if not isinstance(uid, str) or not uid.strip():
                return f"items-json[{i}].uncovered[{j}] must be a non-empty string"
            text = uid.strip()
            if text not in ids:
                ids.append(text)
        out.append({"lens": lens, "uncovered": ids})
    return out


def cmd_pending_replace(args: argparse.Namespace) -> int:
    kind = args.kind.strip().lower()
    if kind != "edge_hole":
        return _fail("kind must be edge_hole")
    parsed = _parse_replace_items(args.items_json)
    if isinstance(parsed, str):
        return _fail(parsed)
    path = pending_path(_slice_dir(args))
    data = load_pending(path)
    kept: list[dict[str, Any]] = []
    removed = 0
    for item in data["items"]:
        same_kind = str(item.get("kind", "")).strip().lower() == kind
        is_open = str(item.get("status", "")).strip().lower() == "open"
        if same_kind and is_open:
            removed += 1
            continue
        kept.append(item)
    data["items"] = kept
    added: list[str] = []
    for row in parsed:
        uncovered = row["uncovered"]
        item = {
            "id": next_pending_id(data["items"]),
            "kind": kind,
            "status": "open",
            "summary": "uncovered " + ", ".join(uncovered),
            "lens": row["lens"],
            "upstream_ref": uncovered[0] if len(uncovered) == 1 else "",
        }
        data["items"].append(item)
        added.append(item["id"])
    try:
        save_pending(path, data)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(
        {
            "ok": True,
            "command": "pending-replace",
            "kind": kind,
            "removed": removed,
            "added": added,
            "ids": added,
        }
    )


def cmd_pending_resolve(args: argparse.Namespace) -> int:
    path = pending_path(_slice_dir(args))
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
    path = pending_path(_slice_dir(args))
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
    from l_ledger_schema import active_slice_dir

    revision_dir = active_slice_dir(args.revision_dir.resolve())
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
    data = load_pending(pending_path(_slice_dir(args)))
    return _ok(
        {
            "ok": True,
            "command": "gate-check",
            "open_count": 0,
            "items_total": len(data.get("items") or []),
        }
    )


def _load_role_consume_rule_ids(
    project_root: Path,
    profile: str,
    *,
    profile_path: Path | None = None,
) -> list[str]:
    try:
        raw = load_compose_template(
            "role-instance",
            project_root,
            profile_id=profile.strip() or None,
            profile_path=profile_path,
        )
    except ComposeTemplateLoadError as exc:
        raise ValueError(f"role-instance unavailable: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"role-instance invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("role-instance root must be an object")
    errors = validate_role_instance(data)
    if errors:
        raise ValueError(f"role-instance invalid: {'; '.join(errors)}")
    policy = data.get("consume_policy")
    if not isinstance(policy, dict):
        raise ValueError("role-instance missing consume_policy")
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("role-instance consume_policy.rules must be non-empty")
    return [str(r["id"]).strip() for r in rules if isinstance(r, dict)]


def _section_order(
    project_root: Path,
    profile: str,
    *,
    profile_path: Path | None = None,
) -> list[str]:
    data = fetch_section_registry(
        project_root,
        profile_id=profile.strip() or None,
        profile_path=profile_path,
    )
    return lens_key_sequence(data)


def cmd_consume_policy_check(args: argparse.Namespace) -> int:
    try:
        runtime = _runtime_profile(args)
        rule_ids = _load_role_consume_rule_ids(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        return _fail(str(exc))
    return _ok(
        {
            "ok": True,
            "command": "consume-policy-check",
            "rule_ids": rule_ids,
            "rules_total": len(rule_ids),
        }
    )


def _load_patch_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read patch: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("patch root must be an object")
    return data


def cmd_disposition_patch_validate(args: argparse.Namespace) -> int:
    from l_ledger_schema import active_slice_dir

    revision_dir = active_slice_dir(args.revision_dir.resolve())
    try:
        runtime = _runtime_profile(args)
        facts = load_facts(facts_path(revision_dir))
        patch = _load_patch_file(args.patch_file.resolve())
        allowed_lenses = _section_order(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
        allowed_rule_ids = _load_role_consume_rule_ids(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
    except (ValueError, FileNotFoundError, OSError, Exception) as exc:  # noqa: BLE001
        return _fail(str(exc))
    errors = validate_disposition_patch(
        patch,
        facts,
        allowed_lenses=allowed_lenses,
        allowed_rule_ids=allowed_rule_ids,
    )
    if errors:
        return _fail("; ".join(errors))
    return _ok(
        {
            "ok": True,
            "command": "disposition-patch-validate",
            "ops_total": len(patch.get("ops") or []),
            "counts": disposition_counts(facts),
        }
    )


def cmd_disposition_patch_apply(args: argparse.Namespace) -> int:
    from l_ledger_schema import active_slice_dir

    revision_dir = active_slice_dir(args.revision_dir.resolve())
    path = facts_path(revision_dir)
    try:
        runtime = _runtime_profile(args)
        facts = load_facts(path)
        patch = _load_patch_file(args.patch_file.resolve())
        allowed_lenses = _section_order(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
        allowed_rule_ids = _load_role_consume_rule_ids(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
    except (ValueError, Exception) as exc:  # noqa: BLE001
        return _fail(str(exc))
    errors = validate_disposition_patch(
        patch,
        facts,
        allowed_lenses=allowed_lenses,
        allowed_rule_ids=allowed_rule_ids,
    )
    if errors:
        return _fail("; ".join(errors))
    try:
        updated = apply_disposition_patch(facts, patch, mutate=False)
        save_facts(
            path,
            updated,
            allowed_lenses=allowed_lenses,
            allowed_rule_ids=allowed_rule_ids,
        )
    except ValueError as exc:
        return _fail(str(exc))
    loaded = load_facts(path)
    return _ok(
        {
            "ok": True,
            "command": "disposition-patch-apply",
            "path": path.as_posix(),
            "ops_total": len(patch.get("ops") or []),
            "counts": disposition_counts(loaded),
            "facts_total": len(loaded),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision-dir", type=Path, required=True)
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

    p_rep = sub.add_parser(
        "pending-replace",
        help="Replace open edge_hole items from a leftover list",
    )
    p_rep.add_argument("--kind", required=True, help="must be edge_hole")
    p_rep.add_argument(
        "--items-json",
        required=True,
        help="JSON array of {lens, uncovered: [F-id, ...]}",
    )
    p_rep.set_defaults(func=cmd_pending_replace)

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

    p_gate = sub.add_parser(
        "gate-check",
        help="Fail if facts or pending store is missing",
    )
    p_gate.set_defaults(func=cmd_gate_check)

    p_cp = sub.add_parser(
        "consume-policy-check",
        help="Fail if role lacks non-empty consume_policy.rules",
    )
    p_cp.set_defaults(func=cmd_consume_policy_check)

    p_pv = sub.add_parser(
        "disposition-patch-validate",
        help="Validate post-intake retag disposition op-list patch",
    )
    p_pv.add_argument("--patch-file", type=Path, required=True)
    p_pv.set_defaults(func=cmd_disposition_patch_validate)

    p_pa = sub.add_parser(
        "disposition-patch-apply",
        help="Apply post-intake retag disposition op-list patch to _facts.json",
    )
    p_pa.add_argument("--patch-file", type=Path, required=True)
    p_pa.set_defaults(func=cmd_disposition_patch_apply)

    args = parser.parse_args()
    if args.command == "disposition-patch-apply":
        from l_ledger_schema import active_slice_dir

        with compose_state_lock(active_slice_dir(args.revision_dir.resolve())):
            return args.func(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
