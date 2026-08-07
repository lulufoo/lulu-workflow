#!/usr/bin/env python3
"""Inductive Gate 3 section machine — fact-native triple store (K4).

Manages three stores under --out-dir (= revision / INDUCTIVE_OUT_DIR):
  - maturity: inductive-scope/<S>.json (via inductive_section_schema)
  - opens:    inductive-opens.json (via opens_schema)
  - facts:    _facts.json (via facts_schema)

Design: docs/domain/archive/compose/archive-2.0/compose-fact-first-k4-fact-native-design.md §6–§7.

Primary subcommands:
    init-pointer / status / check-coverage / list-sections
    activate-section / set-frontier / materialize-section-registry
    seed-decision (writes facts; alias for seed)
    add-open / update-open / settle-open / defer-open / reject-open
    attach-code-refs (O- only); fact update/settle via fact-production-runner
    get-section / view / checkpoint
    clear-section / skip-section / rewind-section / recompose-check

Deprecated (fail-fast): register-ep, update-ep, append-to-section

All subcommands print JSON to stdout and exit 0 on success, exit 1 on failure.
Global flags: --out-dir PATH (required); optional --project-root /
--compose-profile / --compose-cycle-id for section-registry auto-materialize (facet seeds for prompts);
optional --section-registry.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
_SECTION = _SCRIPTS / "section"
_CORE = _SCRIPTS / "core"
for _p in (_HERE, _SECTION, _CORE, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

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
)
from inductive_section_schema import (  # noqa: E402
    ensure_section,
    list_section_keys,
    load_index,
    load_section,
    save_index,
    save_section,
    section_dir,
    section_path,
)
from opens_schema import (  # noqa: E402
    blocking_open_items,
    load_opens,
    mint_open_id,
    next_open_seq,
    opens_path,
    save_opens,
    validate_opens,
)
from facts_schema import (  # noqa: E402
    facts_path,
    filter_by_lens,
    lenses_present,
    load_facts,
    save_facts,
    validate_facts,
)
from kw_facets import (  # noqa: E402
    load_section_registry_facets,
    materialize_section_registry,
    section_registry_path,
)


def _resolve_section_registry_path(
    out_dir: Path, args: argparse.Namespace
) -> Path | None:
    """Section-registry path: --section-registry, else out_dir file, else fetch."""
    explicit = getattr(args, "section_registry", None)
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            _fail(f"section-registry not found: {path}")
        return path
    local = section_registry_path(out_dir)
    if local.is_file():
        return local
    return _try_fetch_section_registry(out_dir, args)


def _compose_fetch_ids(
    args: argparse.Namespace,
) -> tuple[str | None, str | None]:
    profile = (
        getattr(args, "compose_profile", None)
        or getattr(args, "profile", None)
        or ""
    )
    profile = str(profile).strip() or None
    cycle_id = (
        getattr(args, "compose_cycle_id", None)
        or getattr(args, "cycle_id", None)
        or ""
    )
    cycle_id = str(cycle_id).strip() or None
    return profile, cycle_id


def _try_fetch_section_registry(
    out_dir: Path,
    args: argparse.Namespace,
) -> Path | None:
    """Materialize section-registry when --project-root is set.

    Returns None when fetch is unavailable so callers keep the empty-registry
    backward-compatible path.
    """
    root_raw = getattr(args, "project_root", None)
    if not root_raw:
        return None
    root = Path(root_raw).resolve()
    if not root.is_dir():
        return None
    profile, cycle_id = _compose_fetch_ids(args)
    _io = _SCRIPTS / "io"
    if str(_io) not in sys.path:
        sys.path.insert(0, str(_io))
    try:
        from fetch_compose_framework import (  # noqa: WPS433
            FetchComposeFrameworkError,
            fetch_compose_framework,
        )
    except ImportError:
        return None
    try:
        content = fetch_compose_framework(
            "section-registry",
            root,
            profile_id=profile,
            cycle_id=cycle_id,
        )
        return materialize_section_registry(out_dir, content)
    except (FetchComposeFrameworkError, OSError, ValueError):
        return None



def cmd_materialize_section_registry(out_dir: Path, args: argparse.Namespace) -> None:
    """Write section-registry.json under out-dir (--source or --from-fetch)."""
    source = getattr(args, "source", None)
    from_fetch = bool(getattr(args, "from_fetch", False))
    if source and from_fetch:
        _fail(
            "materialize-section-registry: use only one of --source / --from-fetch"
        )
    if source:
        src = Path(source)
        if not src.is_file():
            _fail(f"section-registry source not found: {src}")
        try:
            text = src.read_text(encoding="utf-8")
            path = materialize_section_registry(out_dir, text)
        except (OSError, ValueError) as exc:
            _fail(str(exc))
    elif from_fetch:
        if not getattr(args, "project_root", None):
            _fail(
                "materialize-section-registry --from-fetch requires --project-root"
            )
        path = _try_fetch_section_registry(out_dir, args)
        if path is None:
            _fail(
                "materialize-section-registry --from-fetch failed "
                "(check --project-root / --profile / network)"
            )
    else:
        _fail(
            "materialize-section-registry requires --source PATH or --from-fetch"
        )
    try:
        registry = load_section_registry_facets(path)
    except ValueError as exc:
        _fail(str(exc))
    _ok(
        {
            "path": str(path),
            "seed_lenses": sorted(registry.keys()),
        }
    )



def _pointer_path(out_dir: Path) -> Path:
    return out_dir / "inductive-section-pointer.json"


def _load_pointer(out_dir: Path) -> dict[str, Any]:
    return load_section_pointer(_pointer_path(out_dir))


def _load_opens(out_dir: Path) -> list[dict[str, Any]]:
    return load_opens(opens_path(out_dir))


def _save_opens(out_dir: Path, opens: list[dict[str, Any]]) -> None:
    save_opens(opens_path(out_dir), opens)


def _load_facts_optional(out_dir: Path) -> list[dict[str, Any]]:
    path = facts_path(out_dir)
    if not path.is_file():
        return []
    return load_facts(path)


# ---------------------------------------------------------------------------
# Anchor helpers (P4 init-fidelity: born-with anchors, declare-first)
# ---------------------------------------------------------------------------

def _parse_anchors_arg(raw: str | None) -> list[dict[str, Any]] | None:
    """Parse a declarative ``--anchors`` JSON array string; None when absent.

    Only ensures the payload is a JSON array so a bad arg fails fast; structural
    validation (kind whitelist / value) is deferred to facts_schema.save_facts.
    """
    if raw is None or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        _fail(f"--anchors must be a JSON array: {exc}")
    if not isinstance(parsed, list):
        _fail("--anchors must be a JSON array")
    return parsed


def _clean_code_ref(ref: str) -> str:
    """Drop a trailing line-number parenthetical: 'a.rs::sym (72)' -> 'a.rs::sym'."""
    return re.sub(r"\s*\(\d+\)\s*$", "", ref.strip()).strip()


def _code_ref_segments(cleaned: str) -> list[str]:
    """Split a cleaned code_ref on '::' into non-empty path/symbol segments."""
    return [seg.strip() for seg in cleaned.split("::") if seg.strip()]


def _distribute_code_refs(
    undeclared: list[dict[str, Any]],
    code_refs: list[str],
) -> None:
    """Fallback (§3.4): attach an open's ``code_refs`` to resolved facts whose
    text contains a path/symbol segment (OR match). Unmatched refs stay on the
    open (not projected). Only facts that did not declare anchors participate.
    Mutates the given facts in place.
    """
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


def _allowed_lenses(out_dir: Path) -> list[str]:
    ptr = _load_pointer(out_dir)
    return [str(k).strip().upper() for k in ptr.get("coverage_order") or []]


def _save_facts_inductive(out_dir: Path, facts: list[dict[str, Any]]) -> None:
    """Inductive write path: force allowed_lenses + non-empty lens_tags already asserted."""
    save_facts(facts_path(out_dir), facts, allowed_lenses=_allowed_lenses(out_dir))


def _parse_lens_tags(raw: str) -> list[str]:
    return [t.strip().upper() for t in (raw or "").split(",") if t.strip()]


def _assert_nonempty_lens_tags(tags: list[str], where: str) -> None:
    if not tags:
        _fail(f"{where}: lens_tags must be non-empty (inductive write path)")


def _normalize_detected_under(raw: str | None) -> str | None:
    if raw is None or str(raw).strip() == "":
        return None
    return str(raw).strip().upper()


def _assert_detected_under_allowed(out_dir: Path, detected_under: str | None) -> None:
    """Non-null detected_under must be in coverage_order (same as add-open)."""
    if detected_under is None:
        return
    allowed = set(_allowed_lenses(out_dir))
    if allowed and detected_under not in allowed:
        _fail(
            f"detected_under={detected_under!r} not in "
            f"coverage_order {sorted(allowed)}"
        )


def _commit_facts_then_opens(
    out_dir: Path,
    *,
    facts_before: list[dict[str, Any]],
    facts_after: list[dict[str, Any]],
    opens_after: list[dict[str, Any]],
) -> None:
    """Validate both stores, write facts then opens; roll back facts if opens fails."""
    allowed = _allowed_lenses(out_dir)
    ferrs = validate_facts(facts_after, allowed_lenses=allowed or None)
    if ferrs:
        _fail("; ".join(ferrs))
    oerrs = validate_opens(opens_after)
    if oerrs:
        _fail("; ".join(oerrs))

    try:
        _save_facts_inductive(out_dir, facts_after)
    except (ValueError, OSError) as exc:
        _fail(str(exc))

    try:
        _save_opens(out_dir, opens_after)
    except (ValueError, OSError) as exc:
        # Roll back facts so we never leave discovered orphans with open still open.
        # OSError is the realistic post-validate failure (disk/permission); ValueError
        # remains for schema-layer raises inside save helpers.
        try:
            fpath = facts_path(out_dir)
            if facts_before:
                _save_facts_inductive(out_dir, facts_before)
            elif fpath.is_file():
                fpath.unlink()
        except (ValueError, OSError) as rollback_exc:
            _fail(
                f"opens save failed ({exc}); facts rollback also failed "
                f"({rollback_exc}) — manual repair needed"
            )
        _fail(f"opens save failed after facts write; facts rolled back: {exc}")


def _next_fact_id(facts: list[dict[str, Any]]) -> int:
    """Next F-n sequence (max-based; aligns with opens next_open_seq)."""
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


def _find_open(
    opens: list[dict[str, Any]], open_id: str
) -> dict[str, Any] | None:
    return next((o for o in opens if o.get("id") == open_id), None)


def _find_fact(
    facts: list[dict[str, Any]], fact_id: str
) -> dict[str, Any] | None:
    return next((f for f in facts if f.get("id") == fact_id), None)


def _text_excerpt(text: str, limit: int = 80) -> str:
    t = text.strip()
    return t if len(t) <= limit else t[:limit]


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
    opens = _load_opens(out_dir)
    open_count = len(blocking_open_items(opens))
    section_statuses = {k: v["status"] for k, v in ptr["sections"].items()}
    frontier = {k: v.get("frontier_kw", 0) for k, v in ptr["sections"].items()}
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

    blocking = blocking_open_items(_load_opens(out_dir))
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
    opens = _load_opens(out_dir)
    facts = _load_facts_optional(out_dir)
    fact_counts = lenses_present(facts)

    sections_summary: dict[str, Any] = {}
    for key in ptr["coverage_order"]:
        entry = ptr["sections"][key]
        frontier_kw = entry.get("frontier_kw", 0)
        status = entry["status"]
        path = section_path(out_dir, key)
        if path.exists():
            try:
                doc = load_section(out_dir, key)
                frontier_kw = doc.get("frontier_kw", frontier_kw)
                status = doc.get("status", status)
            except ValueError:
                pass
        key_opens = [
            o for o in opens
            if o.get("detected_under") == key and o.get("status") == "open"
        ]
        key_deferred = [
            o for o in opens
            if o.get("detected_under") == key and o.get("status") == "deferred"
        ]
        sections_summary[key] = {
            "status": status,
            "frontier_kw": frontier_kw,
            "decision_count": fact_counts.get(key, 0),
            "open_count": len(key_opens),
            "deferred_count": len(key_deferred),
            "open_blocking_count": len(
                [o for o in key_opens if o.get("blocking") is True]
            ),
            "section_file_exists": path.exists(),
        }

    _ok({
        "active_section": ptr.get("active_section"),
        "coverage_order": ptr["coverage_order"],
        "sections": sections_summary,
        "total_open_count": sum(
            1 for o in opens if o.get("status") == "open"
        ),
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
    _fail("register-ep is removed (section-SoT). Use add-open / update-open.")


def cmd_update_ep(out_dir: Path, args: argparse.Namespace) -> None:
    _fail("update-ep is removed (section-SoT). Use update-open / settle-open / defer-open.")


def _focus_guard(ptr: dict[str, Any], section: str) -> None:
    active = ptr.get("active_section")
    if section != active:
        _fail(
            f"focus guard: section={section!r} != active_section={active!r}; "
            "call activate-section to switch focus first"
        )


def cmd_seed_decision(out_dir: Path, args: argparse.Namespace) -> None:
    """Append a seed fact (origin.type=seed); optional --section for maturity focus."""
    lens_tags = _parse_lens_tags(args.lens_tags)
    _assert_nonempty_lens_tags(lens_tags, "seed-decision")

    section = (getattr(args, "section", None) or "").strip().upper() or None
    if section:
        ptr = _load_pointer(out_dir)
        _focus_guard(ptr, section)
        doc = ensure_section(out_dir, section)
        if doc["status"] == "untouched":
            doc["status"] = "active"
        try:
            save_section(out_dir, doc)
        except ValueError as exc:
            _fail(str(exc))

    origin_refs = [
        r.strip() for r in (getattr(args, "origin_ref", None) or "").split(",") if r.strip()
    ]
    if not origin_refs:
        # P4.antiseep A1: when L mirrors exist / scope-package contract applies,
        # default origin from Lx/scope-ref.json source_path only — never whole
        # $SCOPE_REF / scope-package.
        from scope_package_convert import (  # noqa: WPS433
            ScopePackageAntiseepError,
            seed_source_path_for_out_dir,
        )
        from scope_package_schema import is_scope_package_path  # noqa: WPS433

        try:
            mirror_source = seed_source_path_for_out_dir(out_dir)
        except ScopePackageAntiseepError as exc:
            _fail(str(exc))
        if mirror_source is not None:
            origin_refs.append(mirror_source)
        else:
            try:
                idx = load_index(out_dir)
                scope_ref = (idx.get("scope_ref") or "").strip()
                if scope_ref:
                    if is_scope_package_path(scope_ref):
                        _fail(
                            "P4.antiseep: seed-decision must not default origin_ref "
                            "to scope-package; require Lx/scope-ref.json source_path mirror"
                        )
                    origin_refs.append(scope_ref)
            except (FileNotFoundError, ValueError):
                pass
        origin_refs.append(_text_excerpt(args.text))

    facts = _load_facts_optional(out_dir)
    fact_id = f"F-{_next_fact_id(facts)}"
    fact: dict[str, Any] = {
        "id": fact_id,
        "text": args.text,
        "lens_tags": lens_tags,
        "origin": {"type": "seed", "ref": origin_refs},
    }
    anchors = _parse_anchors_arg(getattr(args, "anchors", None))
    if anchors:
        fact["anchors"] = anchors
    facts.append(fact)
    try:
        _save_facts_inductive(out_dir, facts)
    except ValueError as exc:
        _fail(str(exc))

    payload: dict[str, Any] = {"id": fact_id, "fact_id": fact_id, "lens_tags": lens_tags}
    if section:
        payload["section"] = section
    if getattr(args, "kw", None) is not None:
        payload["kw_hint"] = args.kw
    _ok(payload)


def cmd_add_open(out_dir: Path, args: argparse.Namespace) -> None:
    """Append an open to inductive-opens.json (no focus-guard)."""
    trigger = (args.trigger or "").strip().lower()
    means = (args.means or "").strip().lower()
    if not trigger or not means:
        _fail("add-open requires --trigger and --means")

    opens = _load_opens(out_dir)
    seq = next_open_seq(opens)
    blocking = str(args.blocking).lower() in {"1", "true", "yes"}
    detected_under = _normalize_detected_under(
        getattr(args, "detected_under", None)
    )
    _assert_detected_under_allowed(out_dir, detected_under)

    open_item: dict[str, Any] = {
        "id": mint_open_id(seq),
        "status": "open",
        "source": {"trigger": trigger, "means": means},
        "detected_under": detected_under,
        "kw": args.kw,
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

    opens.append(open_item)
    try:
        _save_opens(out_dir, opens)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"id": open_item["id"], "detected_under": detected_under})


def cmd_update_open(out_dir: Path, args: argparse.Namespace) -> None:
    """Patch an open by id (doc-level; no --section)."""
    opens = _load_opens(out_dir)
    open_item = _find_open(opens, args.open_id)
    if open_item is None:
        _fail(f"open not found: {args.open_id!r}")
    if open_item.get("status") != "open":
        _fail(f"open {args.open_id!r} is not status=open (got {open_item.get('status')!r})")

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
    if args.trigger is not None or args.means is not None:
        source = dict(open_item.get("source") or {})
        if args.trigger is not None:
            source["trigger"] = args.trigger.strip().lower()
        if args.means is not None:
            source["means"] = args.means.strip().lower()
        open_item["source"] = source
    if getattr(args, "detected_under", None) is not None:
        detected_under = _normalize_detected_under(args.detected_under)
        _assert_detected_under_allowed(out_dir, detected_under)
        open_item["detected_under"] = detected_under
    if getattr(args, "provenance_note", None):
        note = args.provenance_note.strip()
        if note:
            prev = open_item.get("leaning") or ""
            open_item["leaning"] = (prev + "\n" + note).strip() if prev else note

    try:
        _save_opens(out_dir, opens)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"updated": args.open_id, "open": open_item})


def cmd_get_section(out_dir: Path, args: argparse.Namespace) -> None:
    section = args.section.strip().upper()
    try:
        doc = load_section(out_dir, section)
    except FileNotFoundError:
        doc = ensure_section(out_dir, section)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"section": doc})


def cmd_settle_open(out_dir: Path, args: argparse.Namespace) -> None:
    """REMOVED write path (archive-11.0).

    Open→facts settlement moved to fact-production-runner
    (``fact_production_control.py settle-open``). This command never writes
    ``_facts.json``.
    """
    del out_dir, args
    _fail(
        "settle-open fact writes moved to fact-production-runner "
        "($FACT_PRODUCTION_CTL settle-open --revision-dir … --open-id … "
        "--facts-file … --confirm). "
        "G3 section control no longer writes _facts.json for settle."
    )


def cmd_reject_open(out_dir: Path, args: argparse.Namespace) -> None:
    opens = _load_opens(out_dir)
    open_item = _find_open(opens, args.open_id)
    if open_item is None:
        _fail(f"open not found: {args.open_id!r}")
    if open_item.get("status") != "open":
        _fail(f"open {args.open_id!r} is not status=open (got {open_item.get('status')!r})")
    reason = (args.reason or "").strip()
    if not reason:
        _fail("reject-open requires non-empty --reason")
    open_item["status"] = "rejected"
    open_item["reason"] = reason
    open_item["resolved_by"] = []
    try:
        _save_opens(out_dir, opens)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"rejected": args.open_id, "reason": reason})


def cmd_defer_open(out_dir: Path, args: argparse.Namespace) -> None:
    opens = _load_opens(out_dir)
    open_item = _find_open(opens, args.open_id)
    if open_item is None:
        _fail(f"open not found: {args.open_id!r}")
    if open_item.get("status") != "open":
        _fail(f"open {args.open_id!r} is not status=open (got {open_item.get('status')!r})")
    note = (args.note or "").strip()
    if not note:
        _fail("defer-open requires non-empty --note")
    open_item["status"] = "deferred"
    open_item["note"] = note
    open_item["resolved_by"] = []
    try:
        _save_opens(out_dir, opens)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"deferred": args.open_id})


def cmd_update_decision(out_dir: Path, args: argparse.Namespace) -> None:
    """REMOVED write path (archive-11.0).

    Fact text updates moved to fact-production-runner
    (``fact_production_control.py update``). This command never writes
    ``_facts.json``.
    """
    del out_dir, args
    _fail(
        "update-decision fact writes moved to fact-production-runner "
        "($FACT_PRODUCTION_CTL update --revision-dir … --id F-n --text … --confirm). "
        "G3 section control no longer writes _facts.json for update-decision."
    )


def cmd_attach_code_refs(out_dir: Path, args: argparse.Namespace) -> None:
    """Attach code_refs to an open (O- only; facts have no code_refs field)."""
    target_id = args.id.strip()
    refs = [r.strip() for r in args.refs.split(",") if r.strip()]
    if not refs:
        _fail("--refs must provide at least one code ref")
    if not target_id.startswith("O-"):
        _fail(
            f"attach-code-refs only supports O- open ids "
            f"(facts have no code_refs field); got {target_id!r}"
        )

    opens = _load_opens(out_dir)
    open_item = _find_open(opens, target_id)
    if open_item is None:
        _fail(f"open not found: {target_id!r}")
    existing = list(open_item.get("code_refs") or [])
    for ref in refs:
        if ref not in existing:
            existing.append(ref)
    open_item["code_refs"] = existing
    try:
        _save_opens(out_dir, opens)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"id": target_id, "code_refs": existing})


def _resolve_view_scope(out_dir: Path, scope: str) -> list[str]:
    scope = (scope or "all").strip()
    if scope == "all":
        ptr = _load_pointer(out_dir)
        keys = list(ptr.get("coverage_order") or [])
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
        _fail("view --scope code:<glob> not implemented in MVP; use all or ST,IF")
    return [s.strip().upper() for s in scope.split(",") if s.strip()]


def assemble_fidelity_markdown(out_dir: Path, keys: list[str]) -> str:
    """Mechanical assembly of fact texts by lens_tags (view --synthesis off)."""
    facts = _load_facts_optional(out_dir)
    parts: list[str] = []
    for key in keys:
        texts = [
            str(f.get("text", "")).strip()
            for f in facts
            if key in (f.get("lens_tags") or [])
        ]
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
    """Context bundle for view --synthesis on: sections + opens + facts."""
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
            doc = {"key": key, "status": "untouched", "frontier_kw": 0}
        sections.append(
            {
                "key": doc["key"],
                "registry_label": key,
                "order": i,
                "status": doc.get("status"),
                "frontier_kw": doc.get("frontier_kw", 0),
            }
        )
    opens = _load_opens(out_dir)
    facts = _load_facts_optional(out_dir)
    facts_summary = [
        {
            "id": f.get("id"),
            "text": f.get("text"),
            "lens_tags": f.get("lens_tags", []),
            **({"origin": f["origin"]} if "origin" in f else {}),
        }
        for f in facts
    ]
    bundle: dict[str, Any] = {
        "index": index,
        "sections": sections,
        "opens": opens,
        "facts": facts_summary,
    }
    if granularity is not None:
        bundle["granularity"] = granularity
    return bundle


def cmd_view(out_dir: Path, args: argparse.Namespace) -> None:
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
    _fail(
        "append-to-section is removed (section-SoT). "
        "Use seed-decision / update-decision / settle-open."
    )


def cmd_clear_section(out_dir: Path, args: argparse.Namespace) -> None:
    section = args.section.strip().upper()
    target_kw: int = args.target_kw

    ptr = _load_pointer(out_dir)
    active = ptr.get("active_section")

    if section != active:
        _fail(
            f"focus guard: section={section!r} != active_section={active!r}; "
            "call activate-section to switch focus first"
        )

    frontier = ptr["sections"][section].get("frontier_kw", 0)
    if frontier < target_kw:
        _fail(
            f"cannot clear {section!r}: frontier_kw={frontier} < target {target_kw}; "
            "call set-frontier once the section reaches the target maturity"
        )

    # Per-section clear: only opens homed on this lens block (detected_under==section).
    # Global blocking (any lens / null home) remains Exit/check-coverage's job.
    section_blocking = [
        o
        for o in blocking_open_items(_load_opens(out_dir))
        if str(o.get("detected_under") or "").strip().upper() == section
    ]
    if section_blocking:
        _fail(
            f"cannot clear {section!r}: {len(section_blocking)} blocking open "
            f"item(s) under this lens: "
            + ", ".join(str(o.get("id")) for o in section_blocking)
        )

    facts = _load_facts_optional(out_dir)
    lens_facts = filter_by_lens(facts, section)
    if not lens_facts:
        _fail(
            f"cannot clear {section!r}: no facts with lens_tags containing {section!r}; "
            "seed-decision or settle-open first"
        )

    json_path = section_path(out_dir, section)
    if json_path.exists():
        try:
            doc = load_section(out_dir, section)
            if "frontier_kw" in doc:
                ptr = set_frontier(ptr, section, int(doc["frontier_kw"]))
        except ValueError as exc:
            _fail(str(exc))

    updated_ptr = clear_section(ptr, section)
    save_section_pointer(_pointer_path(out_dir), updated_ptr)
    try:
        doc = load_section(out_dir, section) if json_path.exists() else ensure_section(out_dir, section)
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
    doc = ensure_section(out_dir, section)
    doc["status"] = "active"
    try:
        save_section(out_dir, doc)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"rewound_to": section})


def cmd_recompose_check(out_dir: Path, _args: argparse.Namespace) -> None:
    """Audit committed artifacts for G4 recompose self-check (structural).

    Mechanical half:
      - cleared sections have <S>.json
      - no blocking∧open items (from opens list)
      - _index.last_checkpoint == \"shape\"
      - lenses_present(facts) must not include any lens whose pointer is untouched
    """
    ptr = _load_pointer(out_dir)
    errors: list[str] = []

    for key in ptr["coverage_order"]:
        status = ptr["sections"][key]["status"]
        if status == "cleared":
            jp = section_path(out_dir, key)
            if not jp.exists():
                errors.append(f"cleared section {key!r} has no file at {jp}")

    blocking = blocking_open_items(_load_opens(out_dir))
    if blocking:
        errors.append(
            f"{len(blocking)} blocking open item(s) not resolved: "
            + ", ".join(str(o.get("id")) for o in blocking)
        )

    # Facts without maturity ledger (lens present but pointer untouched)
    facts = _load_facts_optional(out_dir)
    present = lenses_present(facts)
    orphan_lenses: list[str] = []
    for lens in sorted(present):
        entry = ptr["sections"].get(lens)
        if entry is None:
            orphan_lenses.append(lens)
            continue
        if entry.get("status") == "untouched":
            orphan_lenses.append(lens)
    if orphan_lenses:
        errors.append(
            "facts present for lenses with untouched section pointer: "
            + ", ".join(orphan_lenses)
        )

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
            "predicates (checkpoint mark + cleared files + no blocking opens + "
            "no facts-without-maturity). Semantic comparison is AI-assessed in "
            "g4-recompose-runner before gate-close G4."
        ),
    }

    ok = len(errors) == 0
    print(json.dumps({"ok": ok, "recompose_check": result}, indent=2, ensure_ascii=False))
    if not ok:
        sys.exit(1)


def _git_head_sha(cwd: Path | None = None) -> str | None:
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
        help="$INDUCTIVE_OUT_DIR: revision dir for inductive state + _facts.json",
    )
    parser.add_argument(
        "--section-registry",
        default=None,
        dest="section_registry",
        metavar="PATH",
        help=(
            "Optional section-registry.json (facet seeds for prompts); "
            "default: <out-dir>/section-registry.json when present"
        ),
    )
    parser.add_argument(
        "--project-root",
        default=None,
        dest="project_root",
        metavar="PATH",
        help="Project root for materialize-section-registry --from-fetch / auto-fetch",
    )
    parser.add_argument(
        "--compose-profile",
        default=None,
        dest="compose_profile",
        metavar="ID",
        help="Compose profile id for framework fetch (section-registry auto-materialize)",
    )
    parser.add_argument(
        "--compose-cycle-id",
        default=None,
        dest="compose_cycle_id",
        metavar="ID",
        help="Cycle id for framework fetch (optional)",
    )

    sub = parser.add_subparsers(dest="subcommand", required=True)

    p = sub.add_parser(
        "materialize-section-registry",
        help="Write section-registry.json under out-dir (intent + facet seeds for prompts)",
    )
    p.add_argument("--source", default=None, metavar="PATH", help="Local JSON file")
    p.add_argument(
        "--from-fetch",
        action="store_true",
        dest="from_fetch",
        help="Fetch section-registry via compose framework (--project-root required)",
    )

    p = sub.add_parser("init-pointer", help="Seed section pointer + _index.json")
    p.add_argument(
        "--sections",
        required=True,
        help="Comma-separated section-registry section_order (init/Exit lens set)",
    )
    p.add_argument("--mandatory", default="", help="Comma-separated mandatory section keys")
    p.add_argument("--cycle-id", default="", help="Cycle id for traceability")
    p.add_argument("--profile", default="", help="Compose profile id (stored on _index)")
    p.add_argument("--scope-ref", default="", dest="scope_ref", help="Upstream scope path")

    sub.add_parser("status", help="Return active_section, statuses, blocking open count")
    sub.add_parser("check-coverage", help="Evaluate G3 gate-close coverage predicate")
    sub.add_parser("list-sections", help="Section statuses + fact/open counts")

    p = sub.add_parser("activate-section", help="Switch active_section focus")
    p.add_argument("--section", required=True, metavar="S")

    p = sub.add_parser("set-frontier", help="Set active section's frontier_kw (0..4)")
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument("--kw", required=True, type=int, metavar="N", help="0..4")

    p = sub.add_parser(
        "seed-decision",
        help="Append a seed fact to _facts.json (origin.type=seed)",
    )
    p.add_argument("--section", default=None, metavar="S", help="Focus + ensure maturity")
    p.add_argument("--lens-tags", required=True, dest="lens_tags", metavar="TAGS")
    p.add_argument("--text", required=True, metavar="TEXT")
    p.add_argument("--origin-ref", default=None, dest="origin_ref", metavar="REFS")
    p.add_argument("--kw", default=None, type=int, metavar="N", help="Hint only; not stored on fact")
    p.add_argument("--rationale", default=None, metavar="TEXT", help="Ignored (compat)")
    p.add_argument(
        "--anchors",
        default=None,
        metavar="JSON",
        help='Declarative anchors: JSON array of {"kind","value"} (P4)',
    )

    p = sub.add_parser("add-open", help="Append an open to inductive-opens.json")
    p.add_argument("--kw", required=True, type=int, metavar="N")
    p.add_argument("--trigger", default=None, metavar="T", help="human|ai (required)")
    p.add_argument(
        "--means",
        default=None,
        metavar="M",
        help=(
            "human_probe|ai_probe|human_direct|human_view|ai_scan|"
            "ai_intent_baseline (required; legacy means migrated on save)"
        ),
    )
    p.add_argument("--problem", required=True, metavar="TEXT")
    p.add_argument("--detected-under", default=None, dest="detected_under", metavar="S")
    p.add_argument("--leaning", default=None, metavar="TEXT")
    p.add_argument("--blocking", default="true", metavar="BOOL")
    p.add_argument("--confidence", default=None, metavar="C")
    p.add_argument("--intent-ref", default=None, dest="intent_ref", metavar="ID")
    p.add_argument("--hangs-under", default=None, dest="hangs_under", metavar="ID")

    p = sub.add_parser("update-open", help="Patch an open by id")
    p.add_argument("--open-id", required=True, dest="open_id", metavar="ID")
    p.add_argument("--problem", default=None, metavar="TEXT")
    p.add_argument("--leaning", default=None, metavar="TEXT")
    p.add_argument("--blocking", default=None, metavar="BOOL")
    p.add_argument("--confidence", default=None, metavar="C")
    p.add_argument("--intent-ref", default=None, dest="intent_ref", metavar="ID")
    p.add_argument("--hangs-under", default=None, dest="hangs_under", metavar="ID")
    p.add_argument("--trigger", default=None, metavar="T")
    p.add_argument("--means", default=None, metavar="M")
    p.add_argument("--detected-under", default=None, dest="detected_under", metavar="S")
    p.add_argument(
        "--provenance-note",
        default=None,
        dest="provenance_note",
        metavar="TEXT",
    )

    p = sub.add_parser("get-section", help="Return maturity <S>.json")
    p.add_argument("--section", required=True, metavar="S")

    p = sub.add_parser(
        "settle-open",
        help="REMOVED write path — use fact-production-runner settle-open",
    )
    p.add_argument("--open-id", required=True, dest="open_id", metavar="ID")
    p.add_argument(
        "--facts-file",
        required=True,
        dest="facts_file",
        metavar="PATH",
        help='JSON array of {"text","lens_tags":[...],"anchors":[{"kind","value"}]?}',
    )
    p.add_argument(
        "--confirm",
        action="store_true",
        help="Required; human whole-batch confirm (archive-10.0 T2 gate)",
    )

    p = sub.add_parser("reject-open", help="Reject an open (status=rejected)")
    p.add_argument("--open-id", required=True, dest="open_id", metavar="ID")
    p.add_argument("--reason", required=True, metavar="TEXT")

    p = sub.add_parser("defer-open", help="Defer an open (status=deferred)")
    p.add_argument("--open-id", required=True, dest="open_id", metavar="ID")
    p.add_argument("--note", required=True, metavar="TEXT")

    p = sub.add_parser(
        "update-decision",
        help="REMOVED write path — use fact-production-runner update",
    )
    p.add_argument("--id", default=None, metavar="F-n", help="Fact id")
    p.add_argument(
        "--decision-id",
        default=None,
        dest="decision_id",
        metavar="F-n",
        help="Compat alias for --id",
    )
    p.add_argument("--text", default=None, metavar="TEXT")
    p.add_argument("--rationale", default=None, metavar="TEXT", help="Ignored (compat)")
    p.add_argument("--section", default=None, metavar="S", help="Ignored (compat)")

    p = sub.add_parser("attach-code-refs", help="Append code_refs to an open (O- only)")
    p.add_argument("--id", required=True, metavar="ID", help="Open id O-n")
    p.add_argument("--refs", required=True, metavar="REFS", help="Comma-separated code refs")

    p = sub.add_parser(
        "view",
        help="Extract a view: synthesis off=fact text by lens; on=bundle",
    )
    p.add_argument("--synthesis", required=True, choices=["off", "on"], metavar="MODE")
    p.add_argument("--scope", default="all", metavar="SCOPE")
    p.add_argument("--granularity", default="", metavar="HINT")

    p = sub.add_parser("register-ep", help="REMOVED — use add-open / update-open")
    p.add_argument("--json", required=True, dest="json", metavar="JSON")

    p = sub.add_parser("update-ep", help="REMOVED — use update-open / settle-open / defer-open")
    p.add_argument("--id", required=True, metavar="EP_ID")
    p.add_argument("--status", required=True, choices=["resolved", "deferred"], metavar="STATUS")
    p.add_argument("--resolution", default=None, metavar="TEXT")

    p = sub.add_parser("append-to-section", help="REMOVED")
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument("--content", required=True, metavar="MARKDOWN")

    p = sub.add_parser("clear-section", help="Clear when frontier+facts+no blocking opens")
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument(
        "--target-kw",
        type=int,
        default=FRONTIER_TARGET_DEFAULT,
        metavar="N",
    )

    p = sub.add_parser("skip-section", help="Mark a section skipped")
    p.add_argument("--section", required=True, metavar="S")
    p.add_argument("--reason", default="", metavar="TEXT")

    p = sub.add_parser("rewind-section", help="Reopen a section")
    p.add_argument("--to", required=True, metavar="S")

    sub.add_parser("recompose-check", help="G4 structural predicates")

    p = sub.add_parser("checkpoint", help="Set _index.last_checkpoint + git sha")
    p.add_argument("--name", required=True, metavar="NAME")

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
        "materialize-section-registry": cmd_materialize_section_registry,
        "seed-decision": cmd_seed_decision,
        "add-open": cmd_add_open,
        "update-open": cmd_update_open,
        "get-section": cmd_get_section,
        "settle-open": cmd_settle_open,
        "reject-open": cmd_reject_open,
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
