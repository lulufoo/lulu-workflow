#!/usr/bin/env python3
"""Parse lens facet lists from section-kw-criteria markdown (fenced JSON).

Design: docs/domain/archive/compose/archive-3.0/compose-inductive-lens-facet-coverage-design.md

Each ``## {LENS}`` section may contain one fenced ``json`` block::

    ```json
    {
      "facets": [
        {"id": "runtime_degradation", "kw": 1, "required": true},
        {"id": "other", "kw": 1, "required": false}
      ]
    }
    ```

Rules for a non-empty facets block:
- ``other`` MUST be present and MUST have ``required: false``.
- ``id`` matches ``[a-z][a-z0-9_]*``; ``kw`` is int 0..4.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

OTHER_FACET_ID = "other"
KW_CRITERIA_BASENAME = "section-kw-criteria.md"
_FACET_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_HEADING_RE = re.compile(r"^##\s+([A-Za-z][A-Za-z0-9_-]*)\s*$", re.MULTILINE)
_FENCED_JSON_RE = re.compile(
    r"```(?:json)?\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)


def kw_criteria_path(out_dir: Path) -> Path:
    """Canonical on-disk kw-criteria path under an inductive revision dir."""
    return Path(out_dir) / KW_CRITERIA_BASENAME


def parse_kw_criteria_facets(markdown: str) -> dict[str, list[dict[str, Any]]]:
    """Return ``{LENS: [facet, ...]}`` for lenses that declare a facets block."""
    if not isinstance(markdown, str) or not markdown.strip():
        return {}

    headings = list(_HEADING_RE.finditer(markdown))
    out: dict[str, list[dict[str, Any]]] = {}
    for i, match in enumerate(headings):
        lens = match.group(1).strip().upper()
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(markdown)
        body = markdown[start:end]
        block = _first_json_fence(body)
        if block is None:
            continue
        out[lens] = _parse_facets_payload(block, lens=lens)
    return out


def materialize_kw_criteria(out_dir: Path, markdown: str) -> Path:
    """Write kw-criteria markdown to ``out_dir`` and validate facet fences."""
    if not isinstance(markdown, str):
        raise ValueError("kw-criteria markdown must be a string")
    parse_kw_criteria_facets(markdown)
    dest = kw_criteria_path(out_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(markdown, encoding="utf-8")
    return dest


def load_kw_criteria_facets(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load and parse facets from a kw-criteria markdown file."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_kw_criteria_facets(text)


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


def must_facets_upto(
    facets: list[dict[str, Any]],
    *,
    target_kw: int,
) -> list[dict[str, Any]]:
    """Must facets with ``kw <= target_kw`` (clear-section gate set)."""
    return [
        f
        for f in facets
        if f.get("required") is True and int(f.get("kw", 0)) <= int(target_kw)
    ]


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
    target_kw: int,
    facets: list[dict[str, Any]],
    opens: list[dict[str, Any]],
    facts: list[dict[str, Any]],
) -> list[str]:
    """Return must facet ids with no non-silence receipt at/below target_kw."""
    lens_u = str(lens).strip().upper()
    missing: list[str] = []
    for facet in must_facets_upto(facets, target_kw=target_kw):
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


def _first_json_fence(body: str) -> dict[str, Any] | None:
    for match in _FENCED_JSON_RE.finditer(body):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "facets" in data:
            return data
    return None


def _parse_facets_payload(
    payload: dict[str, Any],
    *,
    lens: str,
) -> list[dict[str, Any]]:
    raw = payload.get("facets")
    if not isinstance(raw, list):
        raise ValueError(f"{lens}: facets block must contain a facets array")
    if not raw:
        raise ValueError(f"{lens}: facets array must not be empty")

    facets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        where = f"{lens}.facets[{i}]"
        if not isinstance(item, dict):
            raise ValueError(f"{where} must be an object")
        fid = item.get("id")
        if not isinstance(fid, str) or not _FACET_ID_RE.match(fid.strip()):
            raise ValueError(
                f"{where}.id must match [a-z][a-z0-9_]*, got {fid!r}"
            )
        fid = fid.strip()
        if fid in seen:
            raise ValueError(f"{where}: duplicate facet id {fid!r}")
        seen.add(fid)
        kw = item.get("kw")
        if not isinstance(kw, int) or isinstance(kw, bool) or kw < 0 or kw > 4:
            raise ValueError(f"{where}.kw must be int 0..4, got {kw!r}")
        required = item.get("required")
        if not isinstance(required, bool):
            raise ValueError(f"{where}.required must be a bool")
        facets.append({"id": fid, "kw": kw, "required": required})

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
