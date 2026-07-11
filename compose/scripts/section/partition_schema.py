#!/usr/bin/env python3
"""Schema and I/O for revision ``_partition.json`` (compose Partition atoms).

Design SSOT: docs/biz/compose-section-partition-design.md §6.
Shape: JSON array of ``{id, text, home}`` — no envelope.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PARTITION_BASENAME = "_partition.json"
_ATOM_ID_RE = re.compile(r"^A-(\d+)$")
_ATOM_REQUIRED = ("id", "text", "home")


def partition_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / PARTITION_BASENAME


def validate_partition_atoms(
    atoms: Any,
    *,
    allowed_homes: list[str] | None = None,
) -> list[str]:
    """Return validation errors for a partition array."""
    errors: list[str] = []
    if not isinstance(atoms, list):
        return ["partition root must be a JSON array"]
    if not atoms:
        return ["partition array must not be empty"]

    allowed = {h.strip().upper() for h in (allowed_homes or []) if str(h).strip()}
    seen_ids: set[str] = set()
    expected_n = 1

    for index, entry in enumerate(atoms):
        prefix = f"atoms[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in _ATOM_REQUIRED:
            if field not in entry:
                errors.append(f"{prefix}: missing {field}")
        atom_id = entry.get("id")
        if not isinstance(atom_id, str) or not atom_id.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        else:
            aid = atom_id.strip()
            match = _ATOM_ID_RE.match(aid)
            if not match:
                errors.append(f"{prefix}.id must match A-<n> (got {aid!r})")
            else:
                n = int(match.group(1))
                if n != expected_n:
                    errors.append(
                        f"{prefix}.id must be A-{expected_n} (got {aid!r}; "
                        "ids must be contiguous from A-1)",
                    )
                expected_n += 1
            if aid in seen_ids:
                errors.append(f"{prefix}.id duplicate: {aid!r}")
            seen_ids.add(aid)

        text = entry.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{prefix}.text must be a non-empty string")

        home = entry.get("home")
        if not isinstance(home, str) or not home.strip():
            errors.append(f"{prefix}.home must be a non-empty string")
        else:
            home_key = home.strip().upper()
            if home_key != home.strip():
                errors.append(f"{prefix}.home must be uppercase section key")
            if allowed and home_key not in allowed:
                errors.append(
                    f"{prefix}.home {home_key!r} not in section_order "
                    f"{sorted(allowed)}",
                )

        extra = set(entry) - set(_ATOM_REQUIRED)
        if extra:
            errors.append(f"{prefix}: unexpected fields {sorted(extra)}")

    return errors


def normalize_atom(entry: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(entry["id"]).strip(),
        "text": str(entry["text"]).strip(),
        "home": str(entry["home"]).strip().upper(),
    }


def load_partition(path: Path) -> list[dict[str, str]]:
    """Load and validate partition file; raise ValueError on failure."""
    if not path.is_file():
        raise ValueError(f"partition file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid partition JSON: {exc}") from exc
    errors = validate_partition_atoms(data)
    if errors:
        raise ValueError("; ".join(errors))
    return [normalize_atom(entry) for entry in data]


def save_partition(
    path: Path,
    atoms: list[dict[str, Any]],
    *,
    allowed_homes: list[str] | None = None,
) -> None:
    """Validate and write partition array."""
    normalized = [
        {
            "id": str(a.get("id", "")).strip(),
            "text": str(a.get("text", "")).strip(),
            "home": str(a.get("home", "")).strip().upper(),
        }
        for a in atoms
    ]
    errors = validate_partition_atoms(normalized, allowed_homes=allowed_homes)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def filter_i_star(atoms: list[dict[str, str]], section_key: str) -> str:
    """Return prose i_star for one home (blank line between atoms)."""
    key = section_key.strip().upper()
    lines = [a["text"] for a in atoms if a.get("home") == key and a.get("text")]
    return "\n\n".join(lines)


def homes_present(atoms: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for atom in atoms:
        home = atom.get("home", "")
        counts[home] = counts.get(home, 0) + 1
    return counts
