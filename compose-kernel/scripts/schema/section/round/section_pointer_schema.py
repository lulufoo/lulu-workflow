#!/usr/bin/env python3
"""Schema and I/O for tech-plan round-{N}/section-pointer.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from section_registry_schema import section_order

SECTION_STATUSES = frozenset({"pending", "active", "stable", "invalidated"})


def _section_order() -> tuple[str, ...]:
    return section_order()


def round_directory(revision_dir: Path, round_n: int) -> Path:
    """Return revision{R}/round-{N}/ directory path."""
    return revision_dir / f"round-{round_n}"


def section_pointer_path(revision_dir: Path, round_n: int) -> Path:
    """Return canonical section-pointer.json path for a round."""
    return round_directory(revision_dir, round_n) / "section-pointer.json"


def probe_report_path(round_dir: Path, section_key: str, probe_seq: int) -> Path:
    """Return round-{N}/{section}/probe-{seq}.json path."""
    return round_dir / section_key / f"probe-{probe_seq:03d}.json"


def probe_report_relative(section_key: str, probe_seq: int) -> str:
    """Return pointer-relative latest_probe path."""
    return f"{section_key}/probe-{probe_seq:03d}.json"


def _default_section_entry(*, status: str) -> dict[str, Any]:
    return {
        "status": status,
        "latest_probe": None,
        "probe_seq": 0,
        "stable_at_probe": None,
        "invalidated_from": None,
    }


def init_section_pointer(
    *,
    round_n: int,
    revision: int,
    cycle_id: str,
) -> dict[str, Any]:
    """Return a new section pointer with first registry section active."""
    order = _section_order()
    sections: dict[str, dict[str, Any]] = {}
    for index, key in enumerate(order):
        if index == 0:
            sections[key] = _default_section_entry(status="active")
        else:
            sections[key] = _default_section_entry(status="pending")
    return normalize_section_pointer(
        {
            "version": "1",
            "round": round_n,
            "revision": revision,
            "cycle_id": cycle_id,
            "active_section": order[0],
            "section_order": list(order),
            "sections": sections,
        }
    )


def validate_section_pointer(data: dict[str, Any]) -> list[str]:
    """Validate section pointer payload."""
    errors: list[str] = []
    order = _section_order()

    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r} (expected '1')")

    try:
        if int(data.get("round", 0)) < 1:
            errors.append(f"invalid round: {data.get('round')!r}")
    except (TypeError, ValueError):
        errors.append(f"invalid round: {data.get('round')!r}")

    active = str(data.get("active_section", "")).upper()
    if active not in order:
        errors.append(f"invalid active_section: {active!r}")

    pointer_order = data.get("section_order")
    if pointer_order != list(order):
        errors.append("section_order must match registry section_order")

    sections = data.get("sections")
    if not isinstance(sections, dict):
        errors.append("sections must be an object")
        return errors

    for key in order:
        entry = sections.get(key)
        if not isinstance(entry, dict):
            errors.append(f"sections.{key} must be an object")
            continue
        status = str(entry.get("status", "")).lower()
        if status not in SECTION_STATUSES:
            errors.append(f"sections.{key}.status invalid: {status!r}")

    if active and isinstance(sections, dict):
        active_entry = sections.get(active)
        if isinstance(active_entry, dict):
            active_status = str(active_entry.get("status", "")).lower()
            if active_status not in {"active", "stable"}:
                errors.append(
                    f"active_section {active!r} must have status active or stable, "
                    f"got {active_entry.get('status')!r}"
                )

    return errors


def normalize_section_pointer(data: dict[str, Any]) -> dict[str, Any]:
    """Return normalized section pointer."""
    order = _section_order()
    sections_raw = data.get("sections") or {}
    sections: dict[str, dict[str, Any]] = {}
    for key in order:
        entry = dict(sections_raw.get(key) or _default_section_entry(status="pending"))
        entry["status"] = str(entry.get("status", "pending")).lower()
        if entry["status"] not in SECTION_STATUSES:
            entry["status"] = "pending"
        probe_seq = entry.get("probe_seq", 0)
        try:
            entry["probe_seq"] = int(probe_seq)
        except (TypeError, ValueError):
            entry["probe_seq"] = 0
        stable_at = entry.get("stable_at_probe")
        entry["stable_at_probe"] = int(stable_at) if stable_at is not None else None
        latest = entry.get("latest_probe")
        entry["latest_probe"] = str(latest) if latest else None
        invalidated_from = entry.get("invalidated_from")
        entry["invalidated_from"] = str(invalidated_from) if invalidated_from else None
        sections[key] = entry

    return {
        "version": "1",
        "round": int(data["round"]),
        "revision": int(data.get("revision", 1)),
        "cycle_id": str(data.get("cycle_id", "")),
        "active_section": str(data.get("active_section", order[0])).upper(),
        "section_order": list(order),
        "sections": sections,
    }


def load_section_pointer(path: Path) -> dict[str, Any]:
    """Load and validate section pointer from disk."""
    if not path.exists():
        raise FileNotFoundError(f"section pointer not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_section_pointer(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_section_pointer(data)


def save_section_pointer(path: Path, data: dict[str, Any]) -> None:
    """Validate and write section pointer JSON."""
    errors = validate_section_pointer(data)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = normalize_section_pointer(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def next_probe_seq(pointer: dict[str, Any], section_key: str) -> int:
    """Return next probe sequence number for a section."""
    key = section_key.upper()
    entry = pointer["sections"][key]
    return int(entry.get("probe_seq", 0)) + 1


def all_sections_stable(pointer: dict[str, Any]) -> bool:
    """Return True when every section is stable."""
    order = _section_order()
    return all(pointer["sections"][key]["status"] == "stable" for key in order)


def mark_section_stable(pointer: dict[str, Any], section_key: str) -> dict[str, Any]:
    """Mark a section stable; does not change active_section."""
    updated = normalize_section_pointer(pointer)
    order = _section_order()
    key = section_key.upper()
    if key not in order:
        raise ValueError(f"unknown section: {section_key!r}")
    entry = dict(updated["sections"][key])
    entry["status"] = "stable"
    probe_seq = entry.get("probe_seq", 0)
    if probe_seq:
        entry["stable_at_probe"] = probe_seq
    updated["sections"][key] = entry
    return updated


def advance_section(pointer: dict[str, Any]) -> dict[str, Any]:
    """Mark current active section stable and activate the next pending section."""
    updated = normalize_section_pointer(pointer)
    order = _section_order()
    current = updated["active_section"]
    current_index = order.index(current)

    current_entry = dict(updated["sections"][current])
    current_entry["status"] = "stable"
    if current_entry.get("probe_seq"):
        current_entry["stable_at_probe"] = current_entry["probe_seq"]
    updated["sections"][current] = current_entry

    next_key: str | None = None
    for key in order[current_index + 1 :]:
        status = updated["sections"][key]["status"]
        if status in {"pending", "invalidated"}:
            next_key = key
            break

    if next_key is None:
        updated["active_section"] = current
        return updated

    for key in order:
        entry = dict(updated["sections"][key])
        if key == next_key:
            entry["status"] = "active"
            entry["invalidated_from"] = None
        elif entry["status"] == "active" and key != next_key:
            entry["status"] = "stable"
        updated["sections"][key] = entry

    updated["active_section"] = next_key
    return updated


def rewind_section(pointer: dict[str, Any], *, to_section: str, reason: str = "") -> dict[str, Any]:
    """Rewind active section to to_section and invalidate all downstream sections."""
    updated = normalize_section_pointer(pointer)
    order = _section_order()
    target = to_section.upper()
    if target not in order:
        raise ValueError(f"unknown section: {to_section!r}")

    target_index = order.index(target)
    for index, key in enumerate(order):
        entry = dict(updated["sections"][key])
        if index < target_index:
            if entry["status"] == "active":
                entry["status"] = "stable"
        elif key == target:
            entry["status"] = "active"
            entry["invalidated_from"] = None
        else:
            entry["status"] = "invalidated"
            entry["invalidated_from"] = target
            entry["stable_at_probe"] = None
        updated["sections"][key] = entry

    updated["active_section"] = target
    if reason:
        updated["rewind_reason"] = reason
    return updated


def update_latest_probe(
    pointer: dict[str, Any],
    *,
    section_key: str,
    probe_seq: int,
) -> dict[str, Any]:
    """Record latest probe file for a section."""
    updated = normalize_section_pointer(pointer)
    key = section_key.upper()
    entry = dict(updated["sections"][key])
    entry["probe_seq"] = probe_seq
    entry["latest_probe"] = probe_report_relative(key, probe_seq)
    if entry["status"] == "invalidated":
        entry["status"] = "active"
        entry["invalidated_from"] = None
    updated["sections"][key] = entry
    return updated
