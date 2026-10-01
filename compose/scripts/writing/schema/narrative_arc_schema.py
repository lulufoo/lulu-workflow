#!/usr/bin/env python3
"""Schema and I/O for revision ``_narrative-arc.json`` (archive-5.0).

Single-file two-phase narrative arc:
  status ``mapped``      — leaves + fact_ids (phase 1)
  status ``write_ready`` — plus per-leaf chapters (lens → fact_ids) (phase 2)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

NARRATIVE_ARC_BASENAME = "_narrative-arc.json"
# Common G2 display path (filename only; schema is always narrative-arc).
DEFAULT_DISPLAY_ARC_BASENAME = "_narrative-arc.collab.json"
NARRATIVE_ARC_KIND = "narrative-arc"
_STATUS_VALUES = frozenset({"mapped", "write_ready"})
_FACT_ID_RE = re.compile(r"^F-\d+$")
_LENS_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def narrative_arc_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / NARRATIVE_ARC_BASENAME


def _as_id_list(raw: Any, *, prefix: str, errors: list[str]) -> list[str]:
    if not isinstance(raw, list):
        errors.append(f"{prefix} must be an array")
        return []
    out: list[str] = []
    for index, item in enumerate(raw):
        fid = str(item).strip() if item is not None else ""
        if not _FACT_ID_RE.match(fid):
            errors.append(f"{prefix}[{index}] must match F-<n>")
            continue
        out.append(fid)
    return out


def validate_narrative_arc(
    data: Any,
    *,
    facts: list[dict[str, Any]] | None = None,
    allowed_lenses: set[str] | None = None,
) -> list[str]:
    """Validate arc JSON. When ``facts`` is set, enforce full coverage and fact lens ownership."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["narrative_arc root must be an object"]

    if str(data.get("version", "")).strip() != "1":
        errors.append("narrative_arc.version must be '1'")
    kind = str(data.get("kind", "")).strip()
    if kind != NARRATIVE_ARC_KIND:
        errors.append(f"narrative_arc.kind must be {NARRATIVE_ARC_KIND!r}")
    status = str(data.get("status", "")).strip()
    if status not in _STATUS_VALUES:
        errors.append(
            f"narrative_arc.status must be one of {sorted(_STATUS_VALUES)}",
        )

    if "tree" in data and data.get("tree") is not None:
        if not isinstance(data.get("tree"), (dict, list)):
            errors.append("narrative_arc.tree must be an object or array when present")

    for bucket_name in ("excluded", "unresolved"):
        raw = data.get(bucket_name)
        if raw is None:
            continue
        if not isinstance(raw, list):
            errors.append(f"narrative_arc.{bucket_name} must be an array")
            continue
        for index, item in enumerate(raw):
            if isinstance(item, str):
                if not _FACT_ID_RE.match(item.strip()):
                    errors.append(
                        f"narrative_arc.{bucket_name}[{index}] must match F-<n>",
                    )
            elif isinstance(item, dict):
                fid = str(item.get("id") or item.get("fid") or "").strip()
                if not _FACT_ID_RE.match(fid):
                    errors.append(
                        f"narrative_arc.{bucket_name}[{index}].id must match F-<n>",
                    )
            else:
                errors.append(
                    f"narrative_arc.{bucket_name}[{index}] must be string or object",
                )

    leaves = data.get("leaves")
    if not isinstance(leaves, list) or not leaves:
        errors.append("narrative_arc.leaves must be a non-empty array")
        return errors

    seen_leaf_ids: set[str] = set()
    leaf_fact_owner: dict[str, str] = {}
    excluded_ids = _bucket_fact_ids(data.get("excluded"))
    unresolved_ids = _bucket_fact_ids(data.get("unresolved"))

    for index, leaf in enumerate(leaves):
        prefix = f"leaves[{index}]"
        if not isinstance(leaf, dict):
            errors.append(f"{prefix} must be an object")
            continue
        leaf_id = str(leaf.get("id", "")).strip()
        if not leaf_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif leaf_id in seen_leaf_ids:
            errors.append(f"{prefix}.id duplicate: {leaf_id!r}")
        else:
            seen_leaf_ids.add(leaf_id)

        title = str(leaf.get("title", "")).strip()
        if not title:
            errors.append(f"{prefix}.title must be a non-empty string")

        fact_ids = _as_id_list(leaf.get("fact_ids"), prefix=f"{prefix}.fact_ids", errors=errors)
        for fid in fact_ids:
            if fid in excluded_ids:
                errors.append(
                    f"{prefix}.fact_ids contains excluded fact {fid!r}",
                )
            if fid in leaf_fact_owner:
                errors.append(
                    f"fact {fid!r} mapped to multiple leaves: "
                    f"{leaf_fact_owner[fid]!r} and {leaf_id!r}",
                )
            else:
                leaf_fact_owner[fid] = leaf_id

        chapters = leaf.get("chapters")
        if status == "mapped":
            if chapters is None:
                continue
            if not isinstance(chapters, list):
                errors.append(f"{prefix}.chapters must be an array when present")
            continue

        # write_ready
        if not isinstance(chapters, list) or not chapters:
            errors.append(
                f"{prefix}.chapters must be a non-empty array when status=write_ready",
            )
            continue

        chapter_facts: set[str] = set()
        for c_index, chapter in enumerate(chapters):
            cprefix = f"{prefix}.chapters[{c_index}]"
            if not isinstance(chapter, dict):
                errors.append(f"{cprefix} must be an object")
                continue
            lens = str(chapter.get("lens", "")).strip().upper()
            if not _LENS_RE.match(lens):
                errors.append(f"{cprefix}.lens must be an uppercase lens key")
            elif allowed_lenses is not None and lens not in allowed_lenses:
                errors.append(f"{cprefix}.lens {lens!r} not in allowed lenses")
            c_facts = _as_id_list(
                chapter.get("fact_ids"),
                prefix=f"{cprefix}.fact_ids",
                errors=errors,
            )
            if not c_facts:
                errors.append(f"{cprefix}.fact_ids must be non-empty")
            for fid in c_facts:
                if fid not in fact_ids:
                    errors.append(
                        f"{cprefix}.fact_ids {fid!r} not in leaf fact_ids",
                    )
                if fid in chapter_facts:
                    errors.append(
                        f"{prefix} fact {fid!r} in multiple chapters",
                    )
                else:
                    chapter_facts.add(fid)

        missing = sorted(set(fact_ids) - chapter_facts)
        if missing:
            errors.append(
                f"{prefix} write_ready missing chapter membership for: {missing}",
            )

    if unresolved_ids and status == "write_ready":
        errors.append(
            "narrative_arc.status cannot be write_ready while unresolved is non-empty",
        )

    if facts is not None:
        errors.extend(
            _validate_against_facts(
                facts,
                leaf_fact_owner=leaf_fact_owner,
                excluded_ids=excluded_ids,
                unresolved_ids=unresolved_ids,
                status=status,
                data=data,
            )
        )

    return errors


def _bucket_fact_ids(raw: Any) -> set[str]:
    out: set[str] = set()
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, str) and _FACT_ID_RE.match(item.strip()):
            out.add(item.strip())
        elif isinstance(item, dict):
            fid = str(item.get("id") or item.get("fid") or "").strip()
            if _FACT_ID_RE.match(fid):
                out.add(fid)
    return out


def _validate_against_facts(
    facts: list[dict[str, Any]],
    *,
    leaf_fact_owner: dict[str, str],
    excluded_ids: set[str],
    unresolved_ids: set[str],
    status: str,
    data: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    fact_by_id = {
        str(f.get("id", "")).strip(): f
        for f in facts
        if isinstance(f, dict) and str(f.get("id", "")).strip()
    }
    all_ids = set(fact_by_id)
    mapped_or_bucketed = set(leaf_fact_owner) | excluded_ids | unresolved_ids
    missing = sorted(all_ids - mapped_or_bucketed)
    if missing:
        errors.append(f"facts not mapped to any leaf/excluded/unresolved: {missing}")
    unknown = sorted(set(leaf_fact_owner) - all_ids)
    if unknown:
        errors.append(f"leaf fact_ids unknown in facts: {unknown}")

    if status != "write_ready":
        return errors

    unlensed = sorted(
        fid
        for fid, fact in fact_by_id.items()
        if fid in leaf_fact_owner and not str(fact.get("lens") or "").strip()
    )
    if unlensed:
        errors.append(
            f"empty lens blocked at write_ready: {unlensed}",
        )

    for leaf in data.get("leaves") or []:
        if not isinstance(leaf, dict):
            continue
        for chapter in leaf.get("chapters") or []:
            if not isinstance(chapter, dict):
                continue
            lens = str(chapter.get("lens", "")).strip().upper()
            for fid in chapter.get("fact_ids") or []:
                fid_s = str(fid).strip()
                fact = fact_by_id.get(fid_s)
                if not fact:
                    continue
                fact_lens = str(fact.get("lens") or "").strip().upper()
                if lens and lens != fact_lens:
                    errors.append(
                        f"chapter lens {lens!r} is not fact {fid_s} lens {fact_lens!r}",
                    )
    return errors


def normalize_narrative_arc(data: dict[str, Any]) -> dict[str, Any]:
    status = str(data.get("status", "")).strip()
    leaves_out: list[dict[str, Any]] = []
    for leaf in data.get("leaves") or []:
        if not isinstance(leaf, dict):
            continue
        row: dict[str, Any] = {
            "id": str(leaf.get("id", "")).strip(),
            "title": str(leaf.get("title", "")).strip(),
            "fact_ids": [
                str(x).strip()
                for x in (leaf.get("fact_ids") or [])
                if str(x).strip()
            ],
        }
        chapters = leaf.get("chapters")
        if isinstance(chapters, list):
            ch_out = []
            for chapter in chapters:
                if not isinstance(chapter, dict):
                    continue
                ch_out.append(
                    {
                        "lens": str(chapter.get("lens", "")).strip().upper(),
                        "fact_ids": [
                            str(x).strip()
                            for x in (chapter.get("fact_ids") or [])
                            if str(x).strip()
                        ],
                    }
                )
            if ch_out or status == "write_ready":
                row["chapters"] = ch_out
        leaves_out.append(row)

    out: dict[str, Any] = {
        "version": "1",
        "kind": NARRATIVE_ARC_KIND,
        "status": status,
        "leaves": leaves_out,
    }
    for bucket_name in ("excluded", "unresolved"):
        raw = data.get(bucket_name)
        if raw is None:
            continue
        if isinstance(raw, list):
            out[bucket_name] = raw
    if "tree" in data and data.get("tree") is not None:
        out["tree"] = data["tree"]
    return out


def load_narrative_arc(
    path: Path,
    *,
    facts: list[dict[str, Any]] | None = None,
    allowed_lenses: set[str] | None = None,
) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"narrative_arc file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid narrative_arc JSON: {exc}") from exc
    errors = validate_narrative_arc(
        data, facts=facts, allowed_lenses=allowed_lenses,
    )
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_narrative_arc(data)


def save_narrative_arc(
    path: Path,
    data: dict[str, Any],
    *,
    facts: list[dict[str, Any]] | None = None,
    allowed_lenses: set[str] | None = None,
) -> None:
    normalized = normalize_narrative_arc(data if isinstance(data, dict) else {})
    errors = validate_narrative_arc(
        normalized, facts=facts, allowed_lenses=allowed_lenses,
    )
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def is_write_ready(data: dict[str, Any]) -> bool:
    return str(data.get("status", "")).strip() == "write_ready"


def chapter_write_units(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return Write units in document order: one dict per (leaf × lens) chapter.

    ``chapter_id`` is ``{leaf.id}-{lens}`` (fallback ``{leaf.id}-C{index}``).
    Shared by ``list-chapters`` and chapter write-state ``sync``.
    """
    units: list[dict[str, Any]] = []
    for leaf in data.get("leaves") or []:
        if not isinstance(leaf, dict):
            continue
        leaf_id = str(leaf.get("id", "")).strip()
        leaf_title = str(leaf.get("title", "")).strip()
        for index, chapter in enumerate(leaf.get("chapters") or []):
            if not isinstance(chapter, dict):
                continue
            lens = str(chapter.get("lens", "")).strip().upper()
            cid = f"{leaf_id}-{lens}" if leaf_id and lens else f"{leaf_id}-C{index}"
            units.append(
                {
                    "chapter_id": cid,
                    "leaf_id": leaf_id,
                    "leaf_title": leaf_title,
                    "lens": lens,
                    "fact_ids": [
                        str(x).strip()
                        for x in (chapter.get("fact_ids") or [])
                        if str(x).strip()
                    ],
                }
            )
    return units
