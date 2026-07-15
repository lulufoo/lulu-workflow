#!/usr/bin/env python3
"""Schema and I/O for revision ``_chapters.json`` (fact-first display chapters).

Design rationale (source repo, why-only): docs/domain/compose/mechanism-ssot/compose-display-architecture.md;
process how archive: docs/domain/compose/archive-2.0/compose-fact-first-display-layer-design.md §3.4.
Shape: JSON array of chapter objects — no envelope.

Written by Step 4 (global organization); consumed by Step 5 (per-chapter write) and
Step 6 (placement gates L1-L5/C1/Q1). This module validates the **structural**
shape only (M1 scope): field types, ``op`` enum, per-chapter fact-ref shape,
``id``/``fid`` uniqueness. Cross-file consistency against ``_facts.json``
(e.g. L1 exactly-once, L3 legal placement) is a Step 6 gate concern and lives in
``init_compose_validation.py`` (design §11 M2) — not wired here yet.

``anchor_lenses`` is the chapter's **declared** identity (used for L3 legal
placement); ``derived_from`` + ``op`` record chapter genealogy so
merge/split/reorder stays auditable (design §8.2 L5, Grok review Major#8).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CHAPTERS_BASENAME = "_chapters.json"
_FACT_ID_RE = re.compile(r"^F-(\d+)$")
_CHAPTER_REQUIRED = ("id", "anchor_lenses", "derived_from", "op", "facts")
_FACT_REF_REQUIRED = ("fid", "form_lens")
_OP_VALUES = ("keep", "merge", "split", "drop")


def chapters_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / CHAPTERS_BASENAME


def validate_chapters(
    chapters: Any,
    *,
    allowed_lenses: list[str] | None = None,
) -> list[str]:
    """Return validation errors for a chapters array (structural only)."""
    errors: list[str] = []
    if not isinstance(chapters, list):
        return ["chapters root must be a JSON array"]
    if not chapters:
        return ["chapters array must not be empty"]

    allowed = {l.strip().upper() for l in (allowed_lenses or []) if str(l).strip()}
    seen_chapter_ids: set[str] = set()

    for index, entry in enumerate(chapters):
        prefix = f"chapters[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in _CHAPTER_REQUIRED:
            if field not in entry:
                errors.append(f"{prefix}: missing {field}")

        cid = entry.get("id")
        if not isinstance(cid, str) or not cid.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        else:
            cid_norm = cid.strip()
            if cid_norm in seen_chapter_ids:
                errors.append(f"{prefix}.id duplicate: {cid_norm!r}")
            seen_chapter_ids.add(cid_norm)

        anchor_set: set[str] = set()
        anchors = entry.get("anchor_lenses")
        if not isinstance(anchors, list) or not anchors:
            errors.append(f"{prefix}.anchor_lenses must be a non-empty array")
        else:
            for a_index, lens in enumerate(anchors):
                if not isinstance(lens, str) or not lens.strip():
                    errors.append(
                        f"{prefix}.anchor_lenses[{a_index}] must be a non-empty string",
                    )
                    continue
                lens_key = lens.strip().upper()
                if lens_key != lens.strip():
                    errors.append(
                        f"{prefix}.anchor_lenses[{a_index}] must be uppercase lens key",
                    )
                if lens_key in anchor_set:
                    errors.append(f"{prefix}.anchor_lenses duplicate: {lens_key!r}")
                anchor_set.add(lens_key)
                if allowed and lens_key not in allowed:
                    errors.append(
                        f"{prefix}.anchor_lenses[{a_index}] {lens_key!r} not in section_order "
                        f"{sorted(allowed)}",
                    )

        derived = entry.get("derived_from")
        if not isinstance(derived, list) or any(
            not isinstance(d, str) or not d.strip() for d in derived
        ):
            errors.append(
                f"{prefix}.derived_from must be an array of non-empty strings",
            )

        op = entry.get("op")
        if op not in _OP_VALUES:
            errors.append(f"{prefix}.op must be one of {_OP_VALUES} (got {op!r})")

        facts = entry.get("facts")
        if not isinstance(facts, list):
            errors.append(f"{prefix}.facts must be an array")
        elif op == "drop":
            if facts:
                errors.append(
                    f"{prefix}.facts must be empty when op == 'drop' "
                    "(dropped chapter is genealogy-only, not rendered)",
                )
        elif not facts:
            errors.append(
                f"{prefix}.facts must not be empty unless op == 'drop' "
                "(L4 no-empty-rendered-chapter)",
            )
        else:
            seen_fids: set[str] = set()
            for f_index, fact_ref in enumerate(facts):
                fprefix = f"{prefix}.facts[{f_index}]"
                if not isinstance(fact_ref, dict):
                    errors.append(f"{fprefix} must be an object")
                    continue
                for field in _FACT_REF_REQUIRED:
                    if field not in fact_ref:
                        errors.append(f"{fprefix}: missing {field}")

                fid = fact_ref.get("fid")
                if not isinstance(fid, str) or not _FACT_ID_RE.match(fid.strip()):
                    errors.append(f"{fprefix}.fid must match F-<n> (got {fid!r})")
                else:
                    fid_norm = fid.strip()
                    if fid_norm in seen_fids:
                        errors.append(
                            f"{fprefix}.fid duplicate within chapter: {fid_norm!r}",
                        )
                    seen_fids.add(fid_norm)

                # form_lens: intra-file half of §3.4 `form_lens ∈ lens_tags ∩ anchor_lenses`.
                # The `∈ anchor_lenses` + uppercase + section_order checks are decidable here;
                # the `∈ lens_tags` half needs _facts.json → Step 6/L3 gate in M2.
                form_lens = fact_ref.get("form_lens")
                if not isinstance(form_lens, str) or not form_lens.strip():
                    errors.append(f"{fprefix}.form_lens must be a non-empty string")
                else:
                    fl_key = form_lens.strip().upper()
                    if fl_key != form_lens.strip():
                        errors.append(f"{fprefix}.form_lens must be uppercase lens key")
                    if allowed and fl_key not in allowed:
                        errors.append(
                            f"{fprefix}.form_lens {fl_key!r} not in section_order "
                            f"{sorted(allowed)}",
                        )
                    if anchor_set and fl_key not in anchor_set:
                        errors.append(
                            f"{fprefix}.form_lens {fl_key!r} must be one of chapter "
                            f"anchor_lenses {sorted(anchor_set)} "
                            "(∩ lens_tags checked in M2 L3)",
                        )

                extra_f = set(fact_ref) - set(_FACT_REF_REQUIRED)
                if extra_f:
                    errors.append(f"{fprefix}: unexpected fields {sorted(extra_f)}")

        extra = set(entry) - set(_CHAPTER_REQUIRED)
        if extra:
            errors.append(f"{prefix}: unexpected fields {sorted(extra)}")

    return errors


def normalize_chapter(entry: dict[str, Any]) -> dict[str, Any]:
    """Coerce a chapter to canonical shape (uppercase lens keys, stripped strings).

    Defensive on missing keys so it can run **before** validation on the save
    path (matching ``facts_schema.save_facts``
    "normalize→validate" order), keeping lowercase input lenient and consistent
    across all three schemas (Opus review M-1)."""
    return {
        "id": str(entry.get("id", "")).strip(),
        "anchor_lenses": [str(a).strip().upper() for a in (entry.get("anchor_lenses") or [])],
        "derived_from": [str(d).strip() for d in (entry.get("derived_from") or [])],
        "op": str(entry.get("op", "")).strip(),
        "facts": [
            {
                "fid": str(f.get("fid", "")).strip(),
                "form_lens": str(f.get("form_lens", "")).strip().upper(),
            }
            for f in (entry.get("facts") or [])
        ],
    }


def load_chapters(path: Path) -> list[dict[str, Any]]:
    """Load and validate chapters file; raise ValueError on failure."""
    if not path.is_file():
        raise ValueError(f"chapters file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid chapters JSON: {exc}") from exc
    errors = validate_chapters(data)
    if errors:
        raise ValueError("; ".join(errors))
    return [normalize_chapter(entry) for entry in data]


def save_chapters(
    path: Path,
    chapters: list[dict[str, Any]],
    *,
    allowed_lenses: list[str] | None = None,
) -> None:
    """Validate and write chapters array."""
    if not isinstance(chapters, list):
        raise ValueError("chapters root must be a JSON array")
    normalized = [
        normalize_chapter(entry) if isinstance(entry, dict) else entry
        for entry in chapters
    ]
    errors = validate_chapters(normalized, allowed_lenses=allowed_lenses)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def fact_ids_by_chapter(chapters: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Chapter id -> list of assigned fact ids (for L1/L2 cross-checks in M2)."""
    return {c["id"]: [f["fid"] for f in c.get("facts", [])] for c in chapters}


def covered_lenses(chapter: dict[str, Any], facts_by_id: dict[str, list[str]]) -> set[str]:
    """Derived union of lens_tags of facts placed in this chapter (D5; covered ⊇ anchor).

    ``facts_by_id`` maps fact id -> that fact's ``lens_tags`` (from ``_facts.json``).
    """
    result: set[str] = set(chapter.get("anchor_lenses", []))
    for fact_ref in chapter.get("facts", []):
        result |= set(facts_by_id.get(fact_ref.get("fid"), []))
    return result
