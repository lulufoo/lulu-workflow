#!/usr/bin/env python3
"""Demand manifest (``<prefix>-demands.json``) schema helpers.

A *demand manifest* is a producer-side delivery artifact: an atomized list of
demand units that a downstream stage may consume as its ``intent_baseline``
(design rationale, source repo, why-only: ``docs/domain/ssot/compose/inductive-ssot/compose-intent-role-theory.md``;
process how archive: ``docs/domain/archive/compose/archive-1.0/inductive-intent-baseline-source.md`` §5.10).

This module is **mechanical only** — it mints sequential ids, validates shape,
and reads/writes the file. It never enumerates or judges demand *content*: the
atomization (which decisions become which demands, and their summaries) is a
semantic act performed by the AI at delivery time, mirroring the
"scripts never make a semantic judgement about content" rule the inductive
runner already enforces.

Manifest shape::

    {
      "version": 1,
      "id_prefix": "SPEC",
      "demands": [
        {"id": "SPEC-1", "section": "ST", "summary": "..."},
        ...
      ]
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_VERSION = 1


def manifest_filename(id_prefix: str) -> str:
    """Delivery filename derived from the id prefix (``SPEC`` -> ``spec-demands.json``)."""
    prefix = str(id_prefix).strip()
    if not prefix:
        raise ValueError("id_prefix must be non-empty")
    return f"{prefix.lower()}-demands.json"


def _mint_ids(units: list[dict[str, Any]], id_prefix: str) -> list[dict[str, Any]]:
    """Assign ``<prefix>-<n>`` ids to units without one; keep explicit ids as-is.

    Explicit ids give the producer id stability across re-delivery; freshly
    minted numbers fill any gaps, continuing past the highest explicit index.
    """
    prefix = str(id_prefix).strip()
    used: set[int] = set()
    for unit in units:
        raw = str(unit.get("id", "")).strip()
        if raw.startswith(f"{prefix}-"):
            suffix = raw[len(prefix) + 1 :]
            if suffix.isdigit():
                used.add(int(suffix))

    minted: list[dict[str, Any]] = []
    counter = 0
    for unit in units:
        out = {k: v for k, v in unit.items()}
        raw = str(out.get("id", "")).strip()
        if not raw:
            counter += 1
            while counter in used:
                counter += 1
            used.add(counter)
            out["id"] = f"{prefix}-{counter}"
        minted.append(out)
    return minted


def build_manifest(units: list[dict[str, Any]], id_prefix: str) -> dict[str, Any]:
    """Build a manifest dict from AI-enumerated demand units.

    Each unit must carry a non-empty ``section`` and ``summary``; ``id`` is
    optional (minted when absent). Extra keys are preserved verbatim.
    """
    if not isinstance(units, list):
        raise ValueError("units must be a list")
    prefix = str(id_prefix).strip()
    if not prefix:
        raise ValueError("id_prefix must be non-empty")
    demands = _mint_ids([dict(u) for u in units], prefix)
    return {
        "version": MANIFEST_VERSION,
        "id_prefix": prefix,
        "demands": demands,
    }


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """Return a list of shape errors (empty when valid)."""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]

    prefix = str(manifest.get("id_prefix", "")).strip()
    if not prefix:
        errors.append("manifest.id_prefix must be non-empty")

    demands = manifest.get("demands")
    if not isinstance(demands, list):
        return errors + ["manifest.demands must be a list"]

    seen: set[str] = set()
    for idx, demand in enumerate(demands):
        where = f"demands[{idx}]"
        if not isinstance(demand, dict):
            errors.append(f"{where} must be an object")
            continue
        did = str(demand.get("id", "")).strip()
        if not did:
            errors.append(f"{where}.id must be non-empty")
        else:
            if prefix and not did.startswith(f"{prefix}-"):
                errors.append(f"{where}.id {did!r} must start with {prefix!r}-")
            if did in seen:
                errors.append(f"{where}.id {did!r} is duplicated")
            seen.add(did)
        if not str(demand.get("section", "")).strip():
            errors.append(f"{where}.section must be non-empty")
        if not str(demand.get("summary", "")).strip():
            errors.append(f"{where}.summary must be non-empty")
    return errors


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("invalid manifest: " + "; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest file must contain a JSON object")
    return data


def parse_units(raw: str) -> list[dict[str, Any]]:
    """Parse the CLI ``--units-json`` payload (inline JSON or ``@file``)."""
    text = raw.strip()
    if text.startswith("@"):
        text = Path(text[1:]).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("units-json must be a JSON array of demand units")
    return data
