#!/usr/bin/env python3
"""Lens facet *seeds* from section-registry JSON (string list).

Design: docs/domain/archive/compose/archive-3.0/compose-inductive-facet-seeds-and-cmp-design.md

Each section entry may declare::

    "facets": ["runtime degradation", "steady-state rollback"]

Seeds are non-exhaustive inductive reminders (prompt input). They are not a
clear-section gate and do not create open/fact identity fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SECTION_REGISTRY_BASENAME = "section-registry.json"


def section_registry_path(out_dir: Path) -> Path:
    """Canonical on-disk section-registry path under an inductive revision dir."""
    return Path(out_dir) / SECTION_REGISTRY_BASENAME


def validate_facets_list(
    raw: Any,
    *,
    lens: str,
) -> list[str]:
    """Validate and normalize one lens ``facets`` string array."""
    if not isinstance(raw, list):
        raise ValueError(f"{lens}: facets must be an array of strings")
    if not raw:
        raise ValueError(f"{lens}: facets array must not be empty when present")

    out: list[str] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        where = f"{lens}.facets[{i}]"
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{where} must be a non-empty string")
        if isinstance(item, str) and item.strip().startswith("{"):
            raise ValueError(
                f"{where}: object-shaped facets are not allowed; use short strings"
            )
        text = " ".join(item.split())
        key = text.lower()
        if key in seen:
            raise ValueError(f"{where}: duplicate facet seed {text!r}")
        seen.add(key)
        out.append(text)
    return out


def parse_section_registry_facets(
    data: dict[str, Any],
) -> dict[str, list[str]]:
    """Return ``{LENS: [seed, ...]}`` for sections that declare facets."""
    if not isinstance(data, dict):
        raise ValueError("section-registry payload must be an object")
    sections = data.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("section-registry.sections must be an object")
    out: dict[str, list[str]] = {}
    for key, entry in sections.items():
        if not isinstance(entry, dict):
            continue
        if "facets" not in entry:
            continue
        lens = str(key).strip().upper()
        out[lens] = validate_facets_list(entry.get("facets"), lens=lens)
    return out


def materialize_section_registry(out_dir: Path, payload: str | dict[str, Any]) -> Path:
    """Write section-registry JSON to ``out_dir`` (for prompt/seed reads)."""
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid section-registry JSON: {exc}") from exc
    elif isinstance(payload, dict):
        data = payload
    else:
        raise ValueError("section-registry payload must be a string or object")
    if not isinstance(data, dict):
        raise ValueError("section-registry payload must be an object")
    parse_section_registry_facets(data)
    dest = section_registry_path(out_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return dest


def load_section_registry_facets(path: Path) -> dict[str, list[str]]:
    """Load facet seeds from a section-registry JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("section-registry payload must be an object")
    return parse_section_registry_facets(data)


def facets_for_lens(
    registry: dict[str, list[str]],
    lens: str | None,
) -> list[str] | None:
    """Return seed list for lens, or None when undeclared."""
    if not lens:
        return None
    key = str(lens).strip().upper()
    if key not in registry:
        return None
    return registry[key]
