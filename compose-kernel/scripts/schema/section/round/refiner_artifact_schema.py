#!/usr/bin/env python3
"""Schema and I/O for compose stage round-{N}/{section}/refiner-{seq}-{id}.json."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def refiner_artifact_path(
    round_dir: Path,
    section_key: str,
    refiner_seq: int,
    gap_item_id: str,
) -> Path:
    """Return path for a refiner session artifact."""
    safe_id = re.sub(r"[^\w\-]", "-", gap_item_id)
    return round_dir / section_key / f"refiner-{refiner_seq:03d}-{safe_id}.json"


def next_refiner_seq(round_dir: Path, section_key: str) -> int:
    """Return next refiner sequence number for a section directory."""
    section_dir = round_dir / section_key
    if not section_dir.exists():
        return 1
    max_seq = 0
    for path in section_dir.glob("refiner-*.json"):
        match = re.match(r"refiner-(\d+)-", path.name)
        if match:
            max_seq = max(max_seq, int(match.group(1)))
    return max_seq + 1


def validate_refiner_artifact(data: dict[str, Any]) -> list[str]:
    """Validate refiner artifact payload."""
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r} (expected '1')")
    if data.get("kind") != "refiner":
        errors.append(f"invalid kind: {data.get('kind')!r} (expected 'refiner')")
    for field in ("round", "section_key", "gap_item_id", "confirmed_draft"):
        if not str(data.get(field, "")).strip() and field != "confirmed_draft":
            errors.append(f"missing required field: {field}")
    if data.get("confirmed_draft") is None:
        errors.append("missing required field: confirmed_draft")
    try:
        if int(data.get("refiner_seq", 0)) < 1:
            errors.append(f"invalid refiner_seq: {data.get('refiner_seq')!r}")
    except (TypeError, ValueError):
        errors.append(f"invalid refiner_seq: {data.get('refiner_seq')!r}")
    return errors


def normalize_refiner_artifact(data: dict[str, Any]) -> dict[str, Any]:
    """Return normalized refiner artifact."""
    return {
        "version": "1",
        "kind": "refiner",
        "round": int(data["round"]),
        "revision": int(data.get("revision", 1)),
        "cycle_id": str(data.get("cycle_id", "")),
        "section_key": str(data["section_key"]).upper(),
        "gap_item_id": str(data["gap_item_id"]),
        "refiner_seq": int(data["refiner_seq"]),
        "intent_gap": str(data.get("intent_gap", "")),
        "confirmed_draft": str(data["confirmed_draft"]),
        "draft_turns": int(data.get("draft_turns", 1)),
    }


def save_refiner_artifact(path: Path, data: dict[str, Any]) -> None:
    """Validate and write refiner artifact JSON."""
    errors = validate_refiner_artifact(data)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = normalize_refiner_artifact(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
