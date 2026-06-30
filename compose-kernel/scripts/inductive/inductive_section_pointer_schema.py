#!/usr/bin/env python3
"""Schema and I/O for inductive-section-pointer.json.

Tracks Gate 3's parallel section machine for the inductive runner.
Sections are peers; coverage_sections provides the default visit order
and the coverage checklist. Sections can be activated in any order.

Section statuses:
  untouched  - not yet visited
  active     - current focus (only one at a time)
  open       - visited but uncommitted (blocking EPs or user left early)
  cleared    - section bucket built + frontier reached target (file written)
  skipped    - explicitly skipped by user

Per-section frontier_kw (0..4) is the within-section granularity gradient:
  0 = no maturity reached yet; 1..4 = KW1..KW4 (readable -> traceable ->
  boundary-clear -> sign-off-ready). A section is clear enough to leave at the
  target (default 3 = KW3). frontier_kw is an AI-declared maturity marker
  (set-frontier); the script never infers KW truth.

This schema is self-contained and does not reuse any retired section-loop schema.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SECTION_STATUSES = frozenset({"untouched", "active", "open", "cleared", "skipped"})
# Statuses that count as done for the coverage predicate
DONE_STATUSES = frozenset({"cleared", "skipped"})

# Within-section granularity gradient bounds + default clear target.
FRONTIER_KW_MIN = 0
FRONTIER_KW_MAX = 4
FRONTIER_TARGET_DEFAULT = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_section_entry() -> dict[str, Any]:
    return {
        "status": "untouched",
        "frontier_kw": 0,
        "activated_at": None,
        "cleared_at": None,
        "skip_reason": None,
    }


def _clamp_frontier(value: Any) -> int:
    """Coerce a frontier_kw value into the valid 0..4 range."""
    try:
        kw = int(value)
    except (TypeError, ValueError):
        return FRONTIER_KW_MIN
    return max(FRONTIER_KW_MIN, min(FRONTIER_KW_MAX, kw))


def init_section_pointer(
    *,
    coverage_sections: list[str],
    mandatory: list[str],
    cycle_id: str,
) -> dict[str, Any]:
    """Return a new section pointer seeded from coverage_sections.

    No section is pre-activated; the runner activates the first one explicitly.
    """
    sections: dict[str, dict[str, Any]] = {}
    for key in coverage_sections:
        sections[key] = _default_section_entry()

    return normalize_section_pointer(
        {
            "version": "1",
            "cycle_id": cycle_id,
            "active_section": None,
            "coverage_order": list(coverage_sections),
            "mandatory": list(mandatory),
            "sections": sections,
            "updated_at": _now_iso(),
        }
    )


def validate_section_pointer(data: dict[str, Any]) -> list[str]:
    """Return validation error strings (empty list = valid)."""
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r}")

    coverage_order = data.get("coverage_order")
    if not isinstance(coverage_order, list) or not coverage_order:
        errors.append("coverage_order must be a non-empty list")
        return errors

    active = data.get("active_section")
    if active is not None and active not in coverage_order:
        errors.append(f"active_section {active!r} not in coverage_order")

    sections = data.get("sections")
    if not isinstance(sections, dict):
        errors.append("sections must be an object")
        return errors

    for key in coverage_order:
        entry = sections.get(key)
        if not isinstance(entry, dict):
            errors.append(f"sections.{key} must be an object")
            continue
        status = str(entry.get("status", "")).lower()
        if status not in SECTION_STATUSES:
            errors.append(f"sections.{key}.status invalid: {status!r}")
        frontier = entry.get("frontier_kw")
        if not isinstance(frontier, int) or not (
            FRONTIER_KW_MIN <= frontier <= FRONTIER_KW_MAX
        ):
            errors.append(
                f"sections.{key}.frontier_kw must be an int in "
                f"{FRONTIER_KW_MIN}..{FRONTIER_KW_MAX}, got {frontier!r}"
            )

    active_count = sum(
        1
        for k, e in sections.items()
        if isinstance(e, dict) and str(e.get("status", "")).lower() == "active"
    )
    if active_count > 1:
        errors.append(f"only one section may be active; found {active_count}")

    mandatory = data.get("mandatory")
    if not isinstance(mandatory, list):
        errors.append("mandatory must be a list")

    return errors


def normalize_section_pointer(data: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized section pointer dict."""
    coverage_order: list[str] = list(data.get("coverage_order") or [])
    sections_raw = data.get("sections") or {}
    sections: dict[str, dict[str, Any]] = {}

    for key in coverage_order:
        entry = dict(sections_raw.get(key) or _default_section_entry())
        status = str(entry.get("status", "untouched")).lower()
        if status not in SECTION_STATUSES:
            status = "untouched"
        sections[key] = {
            "status": status,
            "frontier_kw": _clamp_frontier(entry.get("frontier_kw", 0)),
            "activated_at": entry.get("activated_at"),
            "cleared_at": entry.get("cleared_at"),
            "skip_reason": entry.get("skip_reason"),
        }

    return {
        "version": "1",
        "cycle_id": str(data.get("cycle_id", "")),
        "active_section": data.get("active_section"),
        "coverage_order": coverage_order,
        "mandatory": list(data.get("mandatory") or []),
        "sections": sections,
        "updated_at": data.get("updated_at") or _now_iso(),
    }


def load_section_pointer(path: Path) -> dict[str, Any]:
    """Load, validate, and normalize section pointer from disk."""
    if not path.exists():
        raise FileNotFoundError(f"inductive-section-pointer not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_section_pointer(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_section_pointer(data)


def save_section_pointer(path: Path, data: dict[str, Any]) -> None:
    """Validate, normalize, and write section pointer to disk."""
    normalized = normalize_section_pointer(data)
    errors = validate_section_pointer(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    normalized["updated_at"] = _now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(normalized, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def activate_section(
    pointer: dict[str, Any], section: str
) -> dict[str, Any]:
    """Switch focus to section; previous active section -> open (if not done)."""
    updated = normalize_section_pointer(pointer)
    order = updated["coverage_order"]
    if section not in order:
        raise ValueError(f"unknown section: {section!r}")

    sections = updated["sections"]
    prev_active = updated.get("active_section")

    if prev_active and prev_active != section:
        prev_entry = dict(sections[prev_active])
        if prev_entry["status"] == "active":
            prev_entry["status"] = "open"
        sections[prev_active] = prev_entry

    target_entry = dict(sections[section])
    if target_entry["status"] not in DONE_STATUSES:
        target_entry["status"] = "active"
        if target_entry["activated_at"] is None:
            target_entry["activated_at"] = _now_iso()
    sections[section] = target_entry

    updated["active_section"] = section
    updated["updated_at"] = _now_iso()
    return updated


def clear_section(
    pointer: dict[str, Any], section: str
) -> dict[str, Any]:
    """Mark section cleared (called after commit-section writes the .md)."""
    updated = normalize_section_pointer(pointer)
    if section not in updated["coverage_order"]:
        raise ValueError(f"unknown section: {section!r}")

    entry = dict(updated["sections"][section])
    entry["status"] = "cleared"
    entry["cleared_at"] = _now_iso()
    updated["sections"][section] = entry
    updated["updated_at"] = _now_iso()
    return updated


def set_frontier(
    pointer: dict[str, Any], section: str, kw: int
) -> dict[str, Any]:
    """Set a section's AI-declared frontier_kw (within-section maturity, 0..4)."""
    updated = normalize_section_pointer(pointer)
    if section not in updated["coverage_order"]:
        raise ValueError(f"unknown section: {section!r}")
    if not isinstance(kw, int) or not (FRONTIER_KW_MIN <= kw <= FRONTIER_KW_MAX):
        raise ValueError(
            f"frontier_kw must be an int in {FRONTIER_KW_MIN}..{FRONTIER_KW_MAX}, got {kw!r}"
        )

    entry = dict(updated["sections"][section])
    entry["frontier_kw"] = kw
    updated["sections"][section] = entry
    updated["updated_at"] = _now_iso()
    return updated


def skip_section(
    pointer: dict[str, Any], section: str, *, reason: str
) -> dict[str, Any]:
    """Mark section skipped with a reason."""
    updated = normalize_section_pointer(pointer)
    if section not in updated["coverage_order"]:
        raise ValueError(f"unknown section: {section!r}")

    entry = dict(updated["sections"][section])
    entry["status"] = "skipped"
    entry["skip_reason"] = reason
    updated["sections"][section] = entry
    updated["updated_at"] = _now_iso()
    return updated


def rewind_section(
    pointer: dict[str, Any], section: str
) -> dict[str, Any]:
    """Reopen a section (G4 audit failure path); clears cleared_at."""
    updated = normalize_section_pointer(pointer)
    if section not in updated["coverage_order"]:
        raise ValueError(f"unknown section: {section!r}")

    sections = updated["sections"]
    prev_active = updated.get("active_section")
    if prev_active and prev_active != section:
        prev_entry = dict(sections[prev_active])
        if prev_entry["status"] == "active":
            prev_entry["status"] = "open"
        sections[prev_active] = prev_entry

    entry = dict(sections[section])
    entry["status"] = "active"
    entry["cleared_at"] = None
    entry["skip_reason"] = None
    if entry["activated_at"] is None:
        entry["activated_at"] = _now_iso()
    sections[section] = entry

    updated["active_section"] = section
    updated["updated_at"] = _now_iso()
    return updated


def check_coverage(pointer: dict[str, Any]) -> dict[str, Any]:
    """Evaluate coverage predicate for G3 gate-close.

    Returns:
        {
            "ok": bool,
            "errors": [str, ...],   # non-empty when ok=False
        }
    """
    errors: list[str] = []
    sections = pointer["sections"]
    coverage_order: list[str] = pointer["coverage_order"]
    mandatory: list[str] = pointer.get("mandatory") or []

    for key in coverage_order:
        entry = sections.get(key, {})
        status = str(entry.get("status", "untouched")).lower()
        if status not in DONE_STATUSES:
            errors.append(f"section {key!r} not done (status={status!r})")

    for key in mandatory:
        entry = sections.get(key, {})
        status = str(entry.get("status", "untouched")).lower()
        if status == "skipped":
            reason = entry.get("skip_reason") or ""
            if not reason.strip():
                errors.append(
                    f"mandatory section {key!r} skipped without reason"
                )
        elif status != "cleared":
            errors.append(
                f"mandatory section {key!r} must be cleared or skipped (status={status!r})"
            )

    return {"ok": len(errors) == 0, "errors": errors}
