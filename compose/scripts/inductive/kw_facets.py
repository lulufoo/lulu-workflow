#!/usr/bin/env python3
"""Lens facet *seeds* from section-registry JSON (string list).

Design: docs/domain/archive/compose/archive-3.0/compose-inductive-facet-seeds-and-cmp-design.md

Each section entry may declare::

    "facets": ["runtime degradation", "steady-state rollback"]

Seeds are non-exhaustive inductive reminders (prompt input). They are not a
clear-section gate and do not create open/fact identity fields.
"""

from __future__ import annotations

from typing import Any


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
        if item.strip().startswith("{"):
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
