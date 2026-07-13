#!/usr/bin/env python3
"""Shared intent_baseline predicates (intent-baseline coverage helpers).

Mechanical only — presence / derivation checks over the delivered demand
manifest and section JSON ``deferred[]`` (section-SoT). Downstream coverage
audits (G5 algorithm A axis 2, d3 direction A) use these to decide whether a
check that a *generative* G3 source already covers should be treated as a
**safety net** (a non-empty result is a regression alarm) rather than a
**primary** discovery. This module never judges content — the "downgrade or
not" call is mechanical (does a manifest exist?), and the semantic matching
stays in the AI runner / eval adapter.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from inductive_section_schema import (  # noqa: E402
    list_section_keys,
    load_section,
    section_path,
)

_MANIFEST_GLOB = "*-demands.json"


def find_demand_manifest(ref_path: str | Path) -> Path | None:
    """Return the demand-manifest sibling of a delivered intent-baseline ref, if any.

    A demand manifest is written beside its producing document as
    ``<prefix>-demands.json``; the consumer locates it by that suffix without
    needing to know the prefix.
    """
    p = Path(ref_path)
    directory = p.parent if p.suffix else p
    if not directory.is_dir():
        return None
    for cand in sorted(directory.glob(_MANIFEST_GLOB)):
        if cand.is_file():
            return cand
    return None


def load_manifest_demands(ref_path: str | Path) -> list[dict[str, Any]]:
    """Load the demand list from the manifest beside ``ref_path`` (empty when absent/bad)."""
    manifest = find_demand_manifest(ref_path)
    if manifest is None:
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    demands = data.get("demands")
    if not isinstance(demands, list):
        return []
    return [d for d in demands if isinstance(d, dict)]


def is_generation_guaranteed(
    intent_baseline_refs: list[Any] | None,
    source: str = "intent_baseline",
) -> bool:
    """True iff ``source`` is the intent baseline AND some ref has a non-empty manifest.

    A non-empty manifest means the demands were in scope at Gate 3, whose close
    gate requires each demand fulfilled-or-deferred — so downstream coverage
    audits for this source become safety nets. Missing / empty manifest
    → False (audits stay primary; degrade when no manifest).
    """
    if source != "intent_baseline":
        return False
    for ref in intent_baseline_refs or []:
        ref_path = ref.get("path") if isinstance(ref, dict) else ref
        if not ref_path:
            continue
        if load_manifest_demands(ref_path):
            return True
    return False


def deferred_intent_refs(out_dir: str | Path) -> set[str]:
    """``intent_ref`` ids carried by *deferred* items in section JSON (S1 silence).

    A demand whose only trace is a deferred item was explicitly skipped by the
    user, so its absence downstream is expected and must not be flagged.

    Reads ``inductive-scope/<S>.json`` deferred arrays (section-SoT). Legacy
    ``exposed-points.json`` is no longer consulted.
    """
    root = Path(out_dir)
    refs: set[str] = set()
    for key in list_section_keys(root):
        path = section_path(root, key)
        if not path.exists():
            continue
        try:
            doc = load_section(root, key)
        except (ValueError, FileNotFoundError):
            continue
        for item in doc.get("deferred") or []:
            ref = item.get("intent_ref")
            if isinstance(ref, str) and ref.strip():
                refs.add(ref.strip())
    return refs
