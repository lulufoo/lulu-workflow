#!/usr/bin/env python3
"""Parse lens facet lists from section-registry JSON.

Design / patch:
- docs/domain/archive/compose/archive-3.0/compose-inductive-lens-facet-coverage-design.md
- .cache/compose-inductive-facet-registry-patch.md (temp)

Each section entry may declare::

    "facets": [
      {"id": "runtime_degradation", "desc": "...", "required": true},
      {"id": "other", "desc": "...", "required": false}
    ]

Rules for a non-empty facets list:
- ``other`` MUST be present and MUST have ``required: false``.
- ``id`` matches ``[a-z][a-z0-9_]*``; ``desc`` non-empty string; no per-facet ``kw``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

OTHER_FACET_ID = "other"
SECTION_REGISTRY_BASENAME = "section-registry.json"
_FACET_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def section_registry_path(out_dir: Path) -> Path:
    """Canonical on-disk section-registry path under an inductive revision dir."""
    return Path(out_dir) / SECTION_REGISTRY_BASENAME


def parse_section_registry_facets(
    data: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Return ``{LENS: [facet, ...]}`` for sections that declare facets."""
    if not isinstance(data, dict):
        raise ValueError("section-registry payload must be an object")
    sections = data.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("section-registry.sections must be an object")
    out: dict[str, list[dict[str, Any]]] = {}
    for key, entry in sections.items():
        if not isinstance(entry, dict):
            continue
        if "facets" not in entry:
            continue
        lens = str(key).strip().upper()
        out[lens] = _parse_facets_list(entry.get("facets"), lens=lens)
    return out


def materialize_section_registry(out_dir: Path, payload: str | dict[str, Any]) -> Path:
    """Write section-registry JSON to ``out_dir`` and validate facet lists."""
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


def load_section_registry_facets(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load and parse facets from a section-registry JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("section-registry payload must be an object")
    return parse_section_registry_facets(data)


def facets_for_lens(
    registry: dict[str, list[dict[str, Any]]],
    lens: str | None,
) -> list[dict[str, Any]] | None:
    """Return facet list for lens, or None when the lens has no declared list."""
    if not lens:
        return None
    key = str(lens).strip().upper()
    if key not in registry:
        return None
    return registry[key]


def facet_ids(facets: list[dict[str, Any]]) -> set[str]:
    return {str(f["id"]) for f in facets}


def must_facets(facets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """All must facets (no per-facet altitude filter)."""
    return [f for f in facets if f.get("required") is True]


def validate_facet_id_for_lens(
    facet_id: str | None,
    *,
    lens: str | None,
    registry: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """Validate open/fact facet_id against registry for a lens.

    - No list on lens → facet_id forbidden.
    - List present → facet_id required and ∈ list.
    """
    errors: list[str] = []
    facets = facets_for_lens(registry, lens)
    has_id = facet_id is not None and str(facet_id).strip() != ""
    if facets is None:
        if has_id:
            errors.append(
                f"facet_id forbidden: lens {lens!r} has no facet list "
                f"(got {facet_id!r})"
            )
        return errors
    if not has_id:
        errors.append(
            f"facet_id required: lens {lens!r} declares a facet list"
        )
        return errors
    fid = str(facet_id).strip()
    if not _FACET_ID_RE.match(fid):
        errors.append(f"facet_id must match [a-z][a-z0-9_]*, got {fid!r}")
        return errors
    allowed = facet_ids(facets)
    if fid not in allowed:
        errors.append(
            f"facet_id {fid!r} not in lens {lens!r} list {sorted(allowed)}"
        )
    return errors


def find_active_open_collision(
    opens: list[dict[str, Any]],
    *,
    detected_under: str | None,
    kw: Any,
    facet_id: str,
    exclude_id: str | None = None,
) -> dict[str, Any] | None:
    """Return status=open with same (detected_under, kw, facet_id), if any."""
    du = (
        None
        if detected_under is None
        else str(detected_under).strip().upper() or None
    )
    fid = str(facet_id).strip()
    for item in opens:
        if item.get("status") != "open":
            continue
        oid = str(item.get("id", "")).strip()
        if exclude_id and oid == exclude_id:
            continue
        item_du = item.get("detected_under")
        item_du = (
            None if item_du is None else str(item_du).strip().upper() or None
        )
        if item_du != du:
            continue
        if item.get("kw") != kw:
            continue
        if str(item.get("facet_id", "")).strip() != fid:
            continue
        return item
    return None


def silence_must_facets(
    *,
    lens: str,
    facets: list[dict[str, Any]],
    opens: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    target_kw: int | None = None,  # noqa: ARG001 — kept for call-site compat
) -> list[str]:
    """Return must facet ids with no receipt (altitude-independent)."""
    del target_kw  # unused; clear checks all must facets every time
    lens_u = str(lens).strip().upper()
    missing: list[str] = []
    for facet in must_facets(facets):
        fid = str(facet["id"])
        if _has_receipt(lens_u, fid, opens=opens, facts=facts):
            continue
        missing.append(fid)
    return missing


def _has_receipt(
    lens: str,
    facet_id: str,
    *,
    opens: list[dict[str, Any]],
    facts: list[dict[str, Any]],
) -> bool:
    for item in opens:
        if str(item.get("facet_id", "")).strip() != facet_id:
            continue
        du = item.get("detected_under")
        du = None if du is None else str(du).strip().upper()
        if du != lens:
            continue
        status = str(item.get("status", "")).strip().lower()
        if status in {"open", "deferred"}:
            return True
    for fact in facts:
        if str(fact.get("facet_id", "")).strip() != facet_id:
            continue
        tags = fact.get("lens_tags") or []
        if not isinstance(tags, list):
            continue
        if lens in {str(t).strip().upper() for t in tags}:
            return True
    return False


def validate_facets_list(
    raw: Any,
    *,
    lens: str,
) -> list[dict[str, Any]]:
    """Validate and normalize one lens ``facets`` array (raises ValueError)."""
    return _parse_facets_list(raw, lens=lens)


def _parse_facets_list(
    raw: Any,
    *,
    lens: str,
) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError(f"{lens}: facets must be an array")
    if not raw:
        raise ValueError(f"{lens}: facets array must not be empty")

    facets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        where = f"{lens}.facets[{i}]"
        if not isinstance(item, dict):
            raise ValueError(f"{where} must be an object")
        if "kw" in item:
            raise ValueError(
                f"{where}: per-facet kw is not allowed "
                f"(use per-lens frontier_kw only)"
            )
        fid = item.get("id")
        if not isinstance(fid, str) or not _FACET_ID_RE.match(fid.strip()):
            raise ValueError(
                f"{where}.id must match [a-z][a-z0-9_]*, got {fid!r}"
            )
        fid = fid.strip()
        if fid in seen:
            raise ValueError(f"{where}: duplicate facet id {fid!r}")
        seen.add(fid)
        desc = item.get("desc")
        if not isinstance(desc, str) or not desc.strip():
            raise ValueError(f"{where}.desc must be a non-empty string")
        required = item.get("required")
        if not isinstance(required, bool):
            raise ValueError(f"{where}.required must be a bool")
        facets.append(
            {"id": fid, "desc": desc.strip(), "required": required}
        )

    if OTHER_FACET_ID not in seen:
        raise ValueError(
            f"{lens}: facets list must include {OTHER_FACET_ID!r}"
        )
    other = next(f for f in facets if f["id"] == OTHER_FACET_ID)
    if other["required"] is not False:
        raise ValueError(
            f"{lens}: facet {OTHER_FACET_ID!r} must have required=false"
        )
    return facets
