#!/usr/bin/env python3
"""Inductive Gate 3 section machine — section-SoT control (design §14).

Manages the section pointer + per-section JSON SoT under inductive-scope/.
Called by inductive_gate_control.py (outer gate spine) and the SKILL via
$INDUCTIVE_G3_SECTION_CTL.

Primary subcommands (section-SoT):
    init-pointer        Seed pointer + _index.json (no EP ledger)
    status              active_section, statuses, blocking open count
    check-coverage      G3 Exit predicate
    list-sections       Section statuses + open/deferred/decision counts
    activate-section    Switch active_section focus
    set-frontier        Cache AI-declared frontier_kw (0..4)
    seed-decision       Append Seed decision (trigger=seed, means=scope)
    add-open / update-open / settle-open / defer-open
    update-decision / attach-code-refs / get-section
    view                synthesis off|on
    checkpoint          last_checkpoint + optional git SHA (G4 baseline)
    clear-section / skip-section / rewind-section / recompose-check

Deprecated (fail-fast): register-ep, update-ep, append-to-section
→ use add-open / update-open / seed-decision / update-decision / settle-open.

All subcommands print JSON to stdout and exit 0 on success, exit 1 on failure.
Global flag: --out-dir PATH (required).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from g3_section_pointer_schema import (  # noqa: E402
    FRONTIER_TARGET_DEFAULT,
    activate_section,
    check_coverage,
    clear_section,
    init_section_pointer,
    load_section_pointer,
    rewind_section,
    save_section_pointer,
    set_frontier,
    skip_section,
    validate_section_pointer,
)
from inductive_section_schema import (  # noqa: E402
    blocking_open_items,
    ensure_section,
    index_path,
    list_section_keys,
    load_index,
    load_section,
    mint_decision_id,
    mint_open_id,
    next_decision_seq,
    next_open_seq,
    save_index,
    save_section,
    section_dir,
    section_path,
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _pointer_path(out_dir: Path) -> Path:
    return out_dir / "inductive-section-pointer.json"


def _load_pointer(out_dir: Path) -> dict[str, Any]:
    return load_section_pointer(_pointer_path(out_dir))


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _ok(payload: dict[str, Any]) -> None:
    print(json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False))


def _fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}, indent=2, ensure_ascii=False))
    sys.exit(1)


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

def cmd_init_pointer(out_dir: Path, args: argparse.Namespace) -> None:
    sections = [s.strip() for s in args.sections.split(",") if s.strip()]
    mandatory = [s.strip() for s in (args.mandatory or "").split(",") if s.strip()]

    if not sections:
        _fail("--sections must provide at least one section key")

    ptr_path = _pointer_path(out_dir)
    if ptr_path.exists():
        _fail(f"section pointer already exists: {ptr_path}")

    cycle_id = args.cycle_id or "_"
    profile = (getattr(args, "profile", None) or "").strip()
    scope_ref = (getattr(args, "scope_ref", None) or "").strip()
    ptr = init_section_pointer(
        coverage_sections=sections,
        mandatory=mandatory,
        cycle_id=cycle_id,
    )
    save_section_pointer(ptr_path, ptr)
    # section-SoT index (design §2); empty sections created lazily on first write
    # No exposed-points.json — opens live in <S>.json (design §10).
    save_index(
        out_dir,
        {
            "version": "1",
            "cycle_id": cycle_id,
            "profile": profile,
            "scope_ref": scope_ref,
            "section_order_ref": "section-registry",
            "last_checkpoint": None,
            "checkpoint_git_sha": None,
        },
    )
    _ok({"message": "section pointer initialized", "sections": sections, "mandatory": mandatory})


def cmd_status(out_dir: Path, _args: argparse.Namespace) -> None:
    ptr = _load_pointer(out_dir)

    open_count = len(blocking_open_items(out_dir))
    section_statuses = {k: v["status"] for k, v in ptr["sections"].items()}
    frontier = {k: v.get("frontier_kw", 0) for k, v in ptr["sections"].items()}
    # Mirror frontier_kw from section JSON when present
    for key in list_section_keys(out_dir):
        try:
            doc = load_section(out_dir, key)
            frontier[key] = doc.get("frontier_kw", frontier.get(key, 0))
            if key in section_statuses:
                section_statuses[key] = doc.get("status", section_statuses[key])
        except (ValueError, FileNotFoundError):
            pass
    _ok({
        "active_section": ptr.get("active_section"),
        "coverage_order": ptr["coverage_order"],
        "sections": section_statuses,
        "frontier": frontier,
        "open_blocking_open_count": open_count,
        "open_blocking_ep_count": open_count,  # alias (deprecated name)
        "mandatory": ptr.get("mandatory", []),
    })


def cmd_check_coverage(out_dir: Path, _args: argparse.Namespace) -> None:
    ptr = _load_pointer(out_dir)

    cov = check_coverage(ptr)

    blocking = blocking_open_items(out_dir)
    if blocking:
        cov["ok"] = False
        cov["errors"].append(
            f"{len(blocking)} blocking open item(s) remain: "
            + ", ".join(str(o.get("id")) for o in blocking)
        )

    print(json.dumps(cov, indent=2, ensure_ascii=False))
    if not cov["ok"]:
        sys.exit(1)


def cmd_list_sections(out_dir: Path, _args: argparse.Namespace) -> None:
    ptr = _load_pointer(out_dir)

    sections_summary: dict[str, Any] = {}
    for key in ptr["coverage_order"]:
        entry = ptr["sections"][key]
        open_items: list[dict[str, Any]] = []
        deferred_count = 0
        decision_count = 0
        frontier_kw = entry.get("frontier_kw", 0)
        status = entry["status"]
        path = section_path(out_dir, key)
        if path.exists():
            try:
                doc = load_section(out_dir, key)
                open_items = list(doc.get("open") or [])
                deferred_count = len(doc.get("deferred") or [])
                decision_count = len(doc.get("decisions") or [])
                frontier_kw = doc.get("frontier_kw", frontier_kw)
                status = doc.get("status", status)
            except ValueError:
                pass
        sections_summary[key] = {
            "status": status,
            "frontier_kw": frontier_kw,
            "decision_count": decision_count,
            "open_count": len(open_items),
            "deferred_count": deferred_count,
            "open_blocking_count": len(
                [o for o in open_items if o.get("blocking") is True]
            ),
            "section_file_exists": path.exists(),
        }

    _ok({
        "active_section": ptr.get("active_section"),
        "coverage_order": ptr["coverage_order"],
        "sections": sections_summary,
        "total_open_count": sum(s["open_count"] for s in sections_summary.values()),
    })


def cmd_activate_section(out_dir: Path, args: argparse.Namespace) -> None:
    section = args.section.strip().upper()
    ptr = _load_pointer(out_dir)

    try:
        updated = activate_section(ptr, section)
    except ValueError as exc:
        _fail(str(exc))

    save_section_pointer(_pointer_path(out_dir), updated)
    _ok({"active_section": section})


def cmd_set_frontier(out_dir: Path, args: argparse.Namespace) -> None:
    section = args.section.strip().upper()
    ptr = _load_pointer(out_dir)
    _focus_guard(ptr, section)

    try:
        updated = set_frontier(ptr, section, args.kw)
    except ValueError as exc:
        _fail(str(exc))

    save_section_pointer(_pointer_path(out_dir), updated)
    # Cache frontier on section JSON SoT as well (design §4.1)
    doc = ensure_section(out_dir, section)
    doc["frontier_kw"] = args.kw
    if doc["status"] == "untouched":
        doc["status"] = "active"
    try:
        save_section(out_dir, doc)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"section": section, "frontier_kw": args.kw})


def cmd_register_ep(out_dir: Path, args: argparse.Namespace) -> None:
    _fail('register-ep is removed (section-SoT). Use add-open / update-open.')



def cmd_update_ep(out_dir: Path, args: argparse.Namespace) -> None:
    _fail('update-ep is removed (section-SoT). Use update-open / settle-open / defer-open.')



def _focus_guard(ptr: dict[str, Any], section: str) -> None:
    active = ptr.get("active_section")
    if section != active:
        _fail(
            f"focus guard: section={section!r} != active_section={active!r}; "
            "call activate-section to switch focus first"
        )


def cmd_seed_decision(out_dir: Path, args: argparse.Namespace) -> None:
    """Append a Seed-era decision with trigger=seed · means=scope (design §5/§14)."""
    section = args.section.strip().upper()
    ptr = _load_pointer(out_dir)
    _focus_guard(ptr, section)

    doc = ensure_section(out_dir, section)
    seq = next_decision_seq(doc)
    decision: dict[str, Any] = {
        "id": mint_decision_id(section, seq),
        "kw": args.kw,
        "text": args.text,
        "trigger": "seed",
        "means": "scope",
        "confidence": "direct",
        "intent_ref": None,
        "code_refs": [],
    }
    if args.rationale:
        decision["rationale"] = args.rationale
    doc["decisions"].append(decision)
    if doc["status"] == "untouched":
        doc["status"] = "active"
    try:
        save_section(out_dir, doc)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"id": decision["id"], "section": section})


def cmd_add_open(out_dir: Path, args: argparse.Namespace) -> None:
    """Append an open point to section JSON (design §6/§14)."""
    section = args.section.strip().upper()
    ptr = _load_pointer(out_dir)
    _focus_guard(ptr, section)

    trigger = (args.trigger or "").strip().lower()
    means = (args.means or "").strip().lower()
    if not trigger or not means:
        _fail("add-open requires --trigger and --means")

    doc = ensure_section(out_dir, section)
    seq = next_open_seq(doc)
    blocking = str(args.blocking).lower() in {"1", "true", "yes"}
    open_item: dict[str, Any] = {
        "id": mint_open_id(section, seq),
        "kw": args.kw,
        "trigger": trigger,
        "means": means,
        "blocking": blocking,
        "problem": args.problem,
    }
    if args.leaning:
        open_item["leaning"] = args.leaning
    if args.confidence:
        open_item["confidence"] = args.confidence
    if args.intent_ref:
        open_item["intent_ref"] = args.intent_ref
    if args.hangs_under:
        open_item["hangs_under"] = args.hangs_under
    doc["open"].append(open_item)
    if doc["status"] == "untouched":
        doc["status"] = "active"
    try:
        save_section(out_dir, doc)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"id": open_item["id"], "section": section})



def cmd_update_open(out_dir: Path, args: argparse.Namespace) -> None:
    """Patch an open item (design §14.2) — dedup / provenance attach path."""
    section = args.section.strip().upper()
    ptr = _load_pointer(out_dir)
    _focus_guard(ptr, section)

    doc = ensure_section(out_dir, section)
    open_item = _find_open(doc, args.open_id)
    if open_item is None:
        _fail(f"open not found: {args.open_id!r}")

    if args.problem is not None:
        open_item["problem"] = args.problem
    if args.leaning is not None:
        open_item["leaning"] = args.leaning
    if args.blocking is not None:
        open_item["blocking"] = str(args.blocking).lower() in {"1", "true", "yes"}
    if args.confidence is not None:
        open_item["confidence"] = args.confidence
    if args.intent_ref is not None:
        open_item["intent_ref"] = args.intent_ref
    if args.hangs_under is not None:
        open_item["hangs_under"] = args.hangs_under
    if args.trigger is not None:
        open_item["trigger"] = args.trigger.strip().lower()
    if args.means is not None:
        open_item["means"] = args.means.strip().lower()
    # Optional provenance note attached into leaning (dedup collide path)
    if getattr(args, "provenance_note", None):
        note = args.provenance_note.strip()
        if note:
            prev = open_item.get("leaning") or ""
            open_item["leaning"] = (prev + "\n" + note).strip() if prev else note

    try:
        save_section(out_dir, doc)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"updated": args.open_id, "section": section, "open": open_item})


def cmd_get_section(out_dir: Path, args: argparse.Namespace) -> None:
    section = args.section.strip().upper()
    try:
        doc = load_section(out_dir, section)
    except FileNotFoundError:
        doc = ensure_section(out_dir, section)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"section": doc})


def _find_open(doc: dict[str, Any], open_id: str) -> dict[str, Any] | None:
    return next((o for o in doc.get("open", []) if o.get("id") == open_id), None)


def _find_decision(doc: dict[str, Any], decision_id: str) -> dict[str, Any] | None:
    return next((d for d in doc.get("decisions", []) if d.get("id") == decision_id), None)


def cmd_settle_open(out_dir: Path, args: argparse.Namespace) -> None:
    """Move open → decisions, inheriting trigger/means/intent_ref (design §14)."""
    section = args.section.strip().upper()
    ptr = _load_pointer(out_dir)
    _focus_guard(ptr, section)

    doc = ensure_section(out_dir, section)
    open_item = _find_open(doc, args.open_id)
    if open_item is None:
        _fail(f"open not found: {args.open_id!r}")

    seq = next_decision_seq(doc)
    decision: dict[str, Any] = {
        "id": mint_decision_id(section, seq),
        "kw": open_item.get("kw", args.kw if hasattr(args, "kw") and args.kw is not None else 1),
        "text": args.text,
        "trigger": open_item["trigger"],
        "means": open_item["means"],
        "confidence": (args.confidence or open_item.get("confidence") or "inferred"),
        "intent_ref": open_item.get("intent_ref"),
        "code_refs": list(open_item.get("code_refs") or []),
    }
    if args.rationale:
        decision["rationale"] = args.rationale
    elif open_item.get("leaning") and not args.rationale:
        # keep leaning only if caller did not supply rationale — optional
        pass

    doc["open"] = [o for o in doc["open"] if o.get("id") != args.open_id]
    doc["decisions"].append(decision)
    try:
        save_section(out_dir, doc)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"decision_id": decision["id"], "settled": args.open_id, "section": section})


def cmd_defer_open(out_dir: Path, args: argparse.Namespace) -> None:
    section = args.section.strip().upper()
    ptr = _load_pointer(out_dir)
    _focus_guard(ptr, section)

    doc = ensure_section(out_dir, section)
    open_item = _find_open(doc, args.open_id)
    if open_item is None:
        _fail(f"open not found: {args.open_id!r}")

    deferred = {
        "id": open_item["id"],
        "kw": open_item.get("kw"),
        "note": args.note or "",
    }
    if open_item.get("intent_ref"):
        deferred["intent_ref"] = open_item["intent_ref"]

    doc["open"] = [o for o in doc["open"] if o.get("id") != args.open_id]
    doc["deferred"].append(deferred)
    try:
        save_section(out_dir, doc)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"deferred": args.open_id, "section": section})


def cmd_update_decision(out_dir: Path, args: argparse.Namespace) -> None:
    section = args.section.strip().upper()
    ptr = _load_pointer(out_dir)
    _focus_guard(ptr, section)

    doc = ensure_section(out_dir, section)
    decision = _find_decision(doc, args.decision_id)
    if decision is None:
        _fail(f"decision not found: {args.decision_id!r}")

    if args.text is not None:
        decision["text"] = args.text
    if args.rationale is not None:
        decision["rationale"] = args.rationale
    try:
        save_section(out_dir, doc)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"updated": args.decision_id, "section": section})


def cmd_attach_code_refs(out_dir: Path, args: argparse.Namespace) -> None:
    section = args.section.strip().upper()
    ptr = _load_pointer(out_dir)
    _focus_guard(ptr, section)

    refs = [r.strip() for r in args.refs.split(",") if r.strip()]
    if not refs:
        _fail("--refs must provide at least one code ref")

    doc = ensure_section(out_dir, section)
    target_id = args.id
    decision = _find_decision(doc, target_id)
    open_item = _find_open(doc, target_id) if decision is None else None
    if decision is None and open_item is None:
        _fail(f"id not found in decisions or open: {target_id!r}")

    item = decision if decision is not None else open_item
    assert item is not None
    existing = list(item.get("code_refs") or [])
    for ref in refs:
        if ref not in existing:
            existing.append(ref)
    item["code_refs"] = existing
    try:
        save_section(out_dir, doc)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"id": target_id, "code_refs": existing, "section": section})


def _resolve_view_scope(out_dir: Path, scope: str) -> list[str]:
    """Resolve --scope into section keys (design §14.3)."""
    scope = (scope or "all").strip()
    if scope == "all":
        ptr = _load_pointer(out_dir)
        keys = list(ptr.get("coverage_order") or [])
        # Also include any on-disk section JSON not in coverage_order
        d = section_dir(out_dir)
        if d.exists():
            for p in sorted(d.glob("*.json")):
                if p.name == "_index.json":
                    continue
                key = p.stem
                if key not in keys:
                    keys.append(key)
        return keys
    if scope.startswith("code:"):
        # MVP: code: glob filter not fully implemented — fail clearly
        _fail("view --scope code:<glob> not implemented in MVP; use all or ST,IF")
    return [s.strip().upper() for s in scope.split(",") if s.strip()]


def assemble_fidelity_markdown(out_dir: Path, keys: list[str]) -> str:
    """Mechanical assembly of decisions[].text (view --synthesis off / compose init)."""
    parts: list[str] = []
    for key in keys:
        path = section_path(out_dir, key)
        if not path.exists():
            continue
        doc = load_section(out_dir, key)
        texts = [str(d.get("text", "")).strip() for d in doc.get("decisions", [])]
        texts = [t for t in texts if t]
        if not texts:
            continue
        parts.append(f"## {key}\n")
        parts.append("\n\n".join(texts))
        parts.append("")
    return "\n".join(parts).rstrip() + ("\n" if parts else "")


def build_view_bundle(
    out_dir: Path, keys: list[str], granularity: str | None = None
) -> dict[str, Any]:
    """Context bundle for view --synthesis on (script packs; AI synthesizes)."""
    try:
        index = load_index(out_dir)
    except FileNotFoundError:
        index = {"version": "1", "cycle_id": "_", "last_checkpoint": None}
    sections: list[dict[str, Any]] = []
    for i, key in enumerate(keys):
        path = section_path(out_dir, key)
        if path.exists():
            doc = load_section(out_dir, key)
        else:
            doc = {
                "key": key,
                "status": "untouched",
                "frontier_kw": 0,
                "decisions": [],
                "open": [],
                "deferred": [],
            }
        sections.append(
            {
                "key": doc["key"],
                "registry_label": key,
                "order": i,
                "status": doc.get("status"),
                "frontier_kw": doc.get("frontier_kw", 0),
                "decisions": doc.get("decisions", []),
                "open": doc.get("open", []),
                "deferred": doc.get("deferred", []),
            }
        )
    bundle: dict[str, Any] = {"index": index, "sections": sections}
    if granularity is not None:
        bundle["granularity"] = granularity
    return bundle


def cmd_view(out_dir: Path, args: argparse.Namespace) -> None:
    """view --synthesis off|on (design §14.3)."""
    synthesis = (args.synthesis or "off").strip().lower()
    if synthesis not in {"off", "on"}:
        _fail("--synthesis must be off or on")
    keys = _resolve_view_scope(out_dir, args.scope)
    if not keys:
        _fail("view scope resolved to empty section list")

    if synthesis == "off":
        md = assemble_fidelity_markdown(out_dir, keys)
        _ok({"synthesis": "off", "scope": keys, "markdown": md})
        return

    granularity = args.granularity or ""
    bundle = build_view_bundle(out_dir, keys, granularity=granularity or None)
    _ok(
        {
            "synthesis": "on",
            "scope": keys,
            "granularity": granularity,
            "bundle": bundle,
        }
    )


def cmd_append_to_section(out_dir: Path, args: argparse.Namespace) -> None:
    _fail('append-to-section is removed (section-SoT). Use seed-decision / update-decision / settle-open.')



def cmd_clear_section(out_dir: Path, args: argparse.Namespace) -> None:
    section = args.section.strip().upper()
    target_kw: int = args.target_kw

    ptr = _load_pointer(out_dir)
    active = ptr.get("active_section")

    # Focus guard
    if section != active:
        _fail(
            f"focus guard: section={section!r} != active_section={active!r}; "
            "call activate-section to switch focus first"
        )

    # Frontier must have reached the target (default KW3).
    frontier = ptr["sections"][section].get("frontier_kw", 0)
    if frontier < target_kw:
        _fail(
            f"cannot clear {section!r}: frontier_kw={frontier} < target {target_kw}; "
            "call set-frontier once the section reaches the target maturity"
        )

    # No blocking-open items for this section (section JSON SoT).
    blocking = blocking_open_items(out_dir, section=section)
    if blocking:
        _fail(
            f"cannot clear {section!r}: {len(blocking)} blocking open item(s): "
            + ", ".join(str(o.get("id")) for o in blocking)
        )

    # Bucket: section JSON with decisions (design §10 — .md no longer SoT)
    json_path = section_path(out_dir, section)
    has_json_body = False
    if json_path.exists():
        try:
            doc = load_section(out_dir, section)
            has_json_body = bool(doc.get("decisions"))
            if "frontier_kw" in doc:
                ptr = set_frontier(ptr, section, int(doc["frontier_kw"]))
        except ValueError as exc:
            _fail(str(exc))
    if not has_json_body:
        _fail(
            f"cannot clear {section!r}: no decisions in {json_path}; "
            "seed-decision or settle-open first"
        )

    updated_ptr = clear_section(ptr, section)
    save_section_pointer(_pointer_path(out_dir), updated_ptr)
    try:
        doc = load_section(out_dir, section)
        doc["status"] = "cleared"
        save_section(out_dir, doc)
    except ValueError as exc:
        _fail(str(exc))

    _ok({"cleared": section, "file": str(json_path)})


def cmd_skip_section(out_dir: Path, args: argparse.Namespace) -> None:
    section = args.section.strip().upper()
    reason: str = args.reason or ""

    ptr = _load_pointer(out_dir)
    active = ptr.get("active_section")

    # Focus guard
    if section != active:
        _fail(
            f"focus guard: section={section!r} != active_section={active!r}; "
            "call activate-section to switch focus first"
        )

    mandatory = ptr.get("mandatory") or []
    if section in mandatory and not reason.strip():
        _fail(f"section {section!r} is mandatory; --reason is required to skip")

    try:
        updated = skip_section(ptr, section, reason=reason)
    except ValueError as exc:
        _fail(str(exc))

    save_section_pointer(_pointer_path(out_dir), updated)
    if section_path(out_dir, section).exists():
        try:
            doc = load_section(out_dir, section)
            doc["status"] = "skipped"
            save_section(out_dir, doc)
        except ValueError as exc:
            _fail(str(exc))
    _ok({"skipped": section, "reason": reason})


def cmd_rewind_section(out_dir: Path, args: argparse.Namespace) -> None:
    section = args.to.strip().upper()
    ptr = _load_pointer(out_dir)

    try:
        updated = rewind_section(ptr, section)
    except ValueError as exc:
        _fail(str(exc))

    save_section_pointer(_pointer_path(out_dir), updated)
    # Keep section JSON status in sync (status command mirrors from JSON)
    doc = ensure_section(out_dir, section)
    doc["status"] = "active"
    try:
        save_section(out_dir, doc)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"rewound_to": section})


def cmd_recompose_check(out_dir: Path, _args: argparse.Namespace) -> None:
    """Audit committed section artifacts for G4 recompose self-check (structural).

    Mechanical half (design Turn 61 / plan C1):
      - cleared sections have <S>.json
      - no blocking∧open items
      - _index.last_checkpoint == \"shape\" (Shape-confirm mark)
      - checkpoint_git_sha reported when recorded (G4 semantic baseline)

    Semantic half (reforms_shape/shape_absorbed meaning vs confirmed spine) is
    assessed by g4-recompose-runner against checkpoint_git_sha / Git history;
    this script only checks that the checkpoint mark exists and artifacts are present.
    Does NOT discover new open points.
    """
    ptr = _load_pointer(out_dir)
    errors: list[str] = []

    # Cleared sections must have section JSON
    for key in ptr["coverage_order"]:
        status = ptr["sections"][key]["status"]
        if status == "cleared":
            jp = section_path(out_dir, key)
            if not jp.exists():
                errors.append(f"cleared section {key!r} has no file at {jp}")

    blocking = blocking_open_items(out_dir)
    if blocking:
        errors.append(
            f"{len(blocking)} blocking open item(s) not resolved: "
            + ", ".join(str(o.get("id")) for o in blocking)
        )

    # Shape baseline mark (replaces frozen architecture_view dependency)
    shape_checkpoint_present = False
    checkpoint_git_sha = None
    try:
        index = load_index(out_dir)
        shape_checkpoint_present = index.get("last_checkpoint") == "shape"
        checkpoint_git_sha = index.get("checkpoint_git_sha")
    except FileNotFoundError:
        errors.append("inductive-scope/_index.json not found (init-pointer / Seed first)")
    except ValueError as exc:
        errors.append(f"_index.json invalid: {exc}")

    if not shape_checkpoint_present:
        errors.append(
            "shape checkpoint missing: last_checkpoint must be 'shape' "
            "(run checkpoint --name shape after Shape-confirm)"
        )

    # reforms_shape (mechanical): checkpoint mark present and no checkpoint-related errors
    reforms_shape = shape_checkpoint_present and not any(
        "shape checkpoint" in e or "_index.json" in e for e in errors
    )

    result = {
        "checkpoint_git_sha": checkpoint_git_sha,
        "reforms_shape": reforms_shape,
        "shape_absorbed": len(errors) == 0,
        "conflicts": [],
        "buildable": None,
        "reversible": None,
        "verifiable": None,
        "errors": errors,
        "_note": (
            "reforms_shape/shape_absorbed here are script-checkable structural "
            "predicates (checkpoint mark + cleared files + no blocking opens). "
            "Semantic comparison of confirmed spine vs HEAD is AI-assessed in "
            "g4-recompose-runner before gate-close G4."
        ),
    }

    ok = len(errors) == 0
    print(json.dumps({"ok": ok, "recompose_check": result}, indent=2, ensure_ascii=False))
    if not ok:
        sys.exit(1)


def _git_head_sha(cwd: Path | None = None) -> str | None:
    """Best-effort HEAD SHA for Shape-confirm baseline (design Turn 61 / I8)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd or Path.cwd()),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    sha = (result.stdout or "").strip()
    return sha or None


def cmd_checkpoint(out_dir: Path, args: argparse.Namespace) -> None:
    """Record last_checkpoint (+ git SHA) on _index.json (Shape-confirm baseline)."""
    name = (args.name or "").strip()
    if not name:
        _fail("--name is required (e.g. shape)")
    try:
        index = load_index(out_dir)
    except FileNotFoundError:
        _fail("inductive-scope/_index.json not found; run init-pointer first")
    except ValueError as exc:
        _fail(str(exc))
    index["last_checkpoint"] = name
    sha = _git_head_sha()
    if sha:
        index["checkpoint_git_sha"] = sha
    try:
        save_index(out_dir, index)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"last_checkpoint": name, "checkpoint_git_sha": index.get("checkpoint_git_sha")})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        metavar="PATH",
        help="$INDUCTIVE_OUT_DIR: directory for inductive state files and artifacts",
    )

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # init-pointer
    p = sub.add_parser("init-pointer", help="Seed section pointer + _index.json (section-SoT)")
    p.add_argument("--sections", required=True, help="Comma-separated coverage_sections")
    p.add_argument("--mandatory", default="", help="Comma-separated mandatory section keys")
    p.add_argument("--cycle-id", default="", help="Cycle id for traceability")
    p.add_argument("--profile", default="", help="Compose profile id (stored on _index)")
    p.add_argument("--scope-ref", default="", dest="scope_ref", help="Upstream scope path (stored on _index)")

    # status
    sub.add_parser("status", help="Return active_section, statuses, blocking open count")

    # check-coverage
    sub.add_parser("check-coverage", help="Evaluate G3 gate-close coverage predicate")

    # list-sections
    sub.add_parser("list-sections", help="Return section statuses + open/deferred/decision counts")

    # activate-section
    p = sub.add_parser("activate-section", help="Switch active_section focus")
    p.add_argument("--section", required=True, metavar="S")

    # set-frontier
    p = sub.add_parser("set-frontier", help="Set active section's frontier_kw (0..4)")
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument("--kw", required=True, type=int, metavar="N", help="0..4 (KW level reached)")

    # seed-decision (section-SoT)
    p = sub.add_parser(
        "seed-decision",
        help="Append a Seed decision to <S>.json (trigger=seed, means=scope)",
    )
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument("--kw", required=True, type=int, metavar="N")
    p.add_argument("--text", required=True, metavar="TEXT")
    p.add_argument("--rationale", default=None, metavar="TEXT")

    # add-open (section-SoT)
    p = sub.add_parser("add-open", help="Append an open point to <S>.json")
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument("--kw", required=True, type=int, metavar="N")
    p.add_argument("--trigger", default=None, metavar="T", help="human|ai (required)")
    p.add_argument(
        "--means",
        default=None,
        metavar="M",
        help="probe|direct|view|ai_scan|intent_baseline (required)",
    )
    p.add_argument("--problem", required=True, metavar="TEXT")
    p.add_argument("--leaning", default=None, metavar="TEXT")
    p.add_argument(
        "--blocking",
        default="true",
        metavar="BOOL",
        help="true|false (default true)",
    )
    p.add_argument("--confidence", default=None, metavar="C")
    p.add_argument("--intent-ref", default=None, dest="intent_ref", metavar="ID")
    p.add_argument("--hangs-under", default=None, dest="hangs_under", metavar="ID")


    # update-open (section-SoT)
    p = sub.add_parser("update-open", help="Patch an open item (dedup / provenance attach)")
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument("--open-id", required=True, dest="open_id", metavar="ID")
    p.add_argument("--problem", default=None, metavar="TEXT")
    p.add_argument("--leaning", default=None, metavar="TEXT")
    p.add_argument("--blocking", default=None, metavar="BOOL")
    p.add_argument("--confidence", default=None, metavar="C")
    p.add_argument("--intent-ref", default=None, dest="intent_ref", metavar="ID")
    p.add_argument("--hangs-under", default=None, dest="hangs_under", metavar="ID")
    p.add_argument("--trigger", default=None, metavar="T")
    p.add_argument("--means", default=None, metavar="M")
    p.add_argument(
        "--provenance-note",
        default=None,
        dest="provenance_note",
        metavar="TEXT",
        help="Append a provenance note into leaning (dedup collide)",
    )

    # get-section (section-SoT)
    p = sub.add_parser("get-section", help="Return <S>.json contents")
    p.add_argument("--section", required=True, metavar="S")

    # settle-open (section-SoT)
    p = sub.add_parser(
        "settle-open",
        help="Move open → decisions (inherit trigger/means/intent_ref)",
    )
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument("--open-id", required=True, dest="open_id", metavar="ID")
    p.add_argument("--text", required=True, metavar="TEXT")
    p.add_argument("--rationale", default=None, metavar="TEXT")
    p.add_argument("--confidence", default=None, metavar="C")

    # defer-open (section-SoT)
    p = sub.add_parser("defer-open", help="Move open → deferred")
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument("--open-id", required=True, dest="open_id", metavar="ID")
    p.add_argument("--note", default="", metavar="TEXT")

    # update-decision (section-SoT)
    p = sub.add_parser("update-decision", help="Patch a decision text/rationale")
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument("--decision-id", required=True, dest="decision_id", metavar="ID")
    p.add_argument("--text", default=None, metavar="TEXT")
    p.add_argument("--rationale", default=None, metavar="TEXT")

    # attach-code-refs (section-SoT)
    p = sub.add_parser(
        "attach-code-refs",
        help="Append code_refs to a decision or open item",
    )
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument("--id", required=True, metavar="ID", help="decision or open id")
    p.add_argument(
        "--refs",
        required=True,
        metavar="REFS",
        help="Comma-separated code refs",
    )

    # view (section-SoT)
    p = sub.add_parser(
        "view",
        help="Extract a view: synthesis off=mechanical markdown; on=context bundle",
    )
    p.add_argument(
        "--synthesis",
        required=True,
        choices=["off", "on"],
        metavar="MODE",
        help="off = decisions[].text assembly; on = JSON context bundle for AI",
    )
    p.add_argument(
        "--scope",
        default="all",
        metavar="SCOPE",
        help="all | ST,IF | (code:glob deferred)",
    )
    p.add_argument(
        "--granularity",
        default="",
        metavar="HINT",
        help="Free-text hint for synthesis:on (passed through; script does not interpret)",
    )

    # register-ep
    p = sub.add_parser("register-ep", help="REMOVED — use add-open / update-open")
    p.add_argument("--json", required=True, dest="json", metavar="JSON", help="EP JSON object")

    # update-ep
    p = sub.add_parser("update-ep", help="REMOVED — use update-open / settle-open / defer-open")
    p.add_argument("--id", required=True, metavar="EP_ID")
    p.add_argument(
        "--status",
        required=True,
        choices=["resolved", "deferred"],
        metavar="STATUS",
    )
    p.add_argument("--resolution", default=None, metavar="TEXT")

    # append-to-section
    p = sub.add_parser(
        "append-to-section",
        help="REMOVED — use seed-decision / update-decision / settle-open",
    )
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument(
        "--content",
        required=True,
        metavar="MARKDOWN",
        help="Markdown fragment to append to <S>.md",
    )

    # clear-section
    p = sub.add_parser(
        "clear-section",
        help="Validate guard + no-blocking-open + frontier>=target, mark cleared",
    )
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument(
        "--target-kw",
        type=int,
        default=FRONTIER_TARGET_DEFAULT,
        metavar="N",
        help=f"Minimum frontier_kw required to clear (default {FRONTIER_TARGET_DEFAULT})",
    )

    # skip-section
    p = sub.add_parser("skip-section", help="Mark a section skipped")
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument("--reason", default="", metavar="TEXT")

    # rewind-section
    p = sub.add_parser("rewind-section", help="Reopen a section (G4 audit failure path)")
    p.add_argument("--to", required=True, metavar="S")

    # recompose-check
    sub.add_parser(
        "recompose-check",
        help="Audit committed artifacts for G4 self-check (structural predicates only)",
    )

    # checkpoint (section-SoT)
    p = sub.add_parser(
        "checkpoint",
        help="Set _index.last_checkpoint + checkpoint_git_sha (Shape-confirm baseline)",
    )
    p.add_argument("--name", required=True, metavar="NAME", help="e.g. shape")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    out_dir = Path(args.out_dir)

    dispatch = {
        "init-pointer": cmd_init_pointer,
        "status": cmd_status,
        "check-coverage": cmd_check_coverage,
        "list-sections": cmd_list_sections,
        "activate-section": cmd_activate_section,
        "set-frontier": cmd_set_frontier,
        "seed-decision": cmd_seed_decision,
        "add-open": cmd_add_open,
        "update-open": cmd_update_open,
        "get-section": cmd_get_section,
        "settle-open": cmd_settle_open,
        "defer-open": cmd_defer_open,
        "update-decision": cmd_update_decision,
        "attach-code-refs": cmd_attach_code_refs,
        "view": cmd_view,
        "register-ep": cmd_register_ep,
        "update-ep": cmd_update_ep,
        "append-to-section": cmd_append_to_section,
        "clear-section": cmd_clear_section,
        "skip-section": cmd_skip_section,
        "rewind-section": cmd_rewind_section,
        "recompose-check": cmd_recompose_check,
        "checkpoint": cmd_checkpoint,
    }

    handler = dispatch.get(args.subcommand)
    if handler is None:
        _fail(f"unknown subcommand: {args.subcommand!r}")

    handler(out_dir, args)


if __name__ == "__main__":
    main()
