#!/usr/bin/env python3
"""Schema and I/O for revision ``_chapter-placement.json`` (archive-3.0 Step 4′.C).

Placement SoT: ``(fid → chapter_id × form_lens_id)``. ``lens_key`` is joined
from ``_lens-themes.json``. ``_chapters.json`` is retired.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CHAPTER_PLACEMENT_BASENAME = "_chapter-placement.json"
_FL_ID_RE = re.compile(r"^FL-(\d+)$")
_FACT_ID_RE = re.compile(r"^F-(\d+)$")
_PLACEMENT_VALUES = ("mechanical", "ai_resolved")


def chapter_placement_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / CHAPTER_PLACEMENT_BASENAME


def validate_chapter_placement(
    data: Any,
    *,
    known_fl_ids: set[str] | None = None,
    chapter_ids: set[str] | None = None,
    fl_to_chapter: dict[str, str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["chapter_placement root must be an object"]
    if str(data.get("version", "")).strip() != "1":
        errors.append("chapter_placement.version must be '1'")
    if str(data.get("$schema_id", "")).strip() not in ("", "chapter-placement"):
        errors.append("chapter_placement.$schema_id must be 'chapter-placement'")

    chapters = data.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        return errors + ["chapter_placement.chapters must be a non-empty array"]

    seen_fid: set[str] = set()
    for index, chapter in enumerate(chapters):
        prefix = f"chapters[{index}]"
        if not isinstance(chapter, dict):
            errors.append(f"{prefix} must be an object")
            continue
        cid = str(chapter.get("id", "")).strip()
        if not cid:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif chapter_ids is not None and cid not in chapter_ids:
            errors.append(f"{prefix}.id {cid!r} not in chapter-framework")

        facts = chapter.get("facts")
        if not isinstance(facts, list):
            errors.append(f"{prefix}.facts must be an array")
            continue
        if not facts:
            errors.append(f"{prefix}.facts must not be empty (rendered chapter)")

        for f_index, fact_ref in enumerate(facts):
            fprefix = f"{prefix}.facts[{f_index}]"
            if not isinstance(fact_ref, dict):
                errors.append(f"{fprefix} must be an object")
                continue
            fid = str(fact_ref.get("fid", "")).strip()
            if not _FACT_ID_RE.match(fid):
                errors.append(f"{fprefix}.fid must match F-<n>")
            elif fid in seen_fid:
                errors.append(f"{fprefix}.fid duplicate across placement: {fid!r}")
            else:
                seen_fid.add(fid)

            fl = str(fact_ref.get("form_lens_id", "")).strip()
            if not _FL_ID_RE.match(fl):
                errors.append(f"{fprefix}.form_lens_id must match FL-<n>")
            else:
                if known_fl_ids is not None and fl not in known_fl_ids:
                    errors.append(f"{fprefix}.form_lens_id {fl!r} not in themes")
                if fl_to_chapter is not None and fl_to_chapter.get(fl) != cid:
                    errors.append(
                        f"{fprefix}.form_lens_id {fl!r} belongs to chapter "
                        f"{fl_to_chapter.get(fl)!r}, not {cid!r}",
                    )

            placement = fact_ref.get("placement")
            if placement not in _PLACEMENT_VALUES:
                errors.append(
                    f"{fprefix}.placement must be one of {_PLACEMENT_VALUES}",
                )
            if placement == "ai_resolved":
                cands = fact_ref.get("candidates")
                if cands is not None:
                    if not isinstance(cands, list) or not cands:
                        errors.append(f"{fprefix}.candidates must be a non-empty array")
                    else:
                        for c in cands:
                            if not _FL_ID_RE.match(str(c).strip()):
                                errors.append(
                                    f"{fprefix}.candidates entry must match FL-<n>",
                                )

    return errors


def normalize_chapter_placement(data: dict[str, Any]) -> dict[str, Any]:
    chapters_out = []
    for chapter in data.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        facts_out = []
        for fact_ref in chapter.get("facts") or []:
            if not isinstance(fact_ref, dict):
                continue
            row: dict[str, Any] = {
                "fid": str(fact_ref.get("fid", "")).strip(),
                "form_lens_id": str(fact_ref.get("form_lens_id", "")).strip(),
                "placement": str(fact_ref.get("placement", "")).strip(),
            }
            if row["placement"] == "ai_resolved" and fact_ref.get("candidates"):
                row["candidates"] = [
                    str(c).strip() for c in fact_ref.get("candidates") or []
                ]
            facts_out.append(row)
        chapters_out.append(
            {
                "id": str(chapter.get("id", "")).strip(),
                "facts": facts_out,
            }
        )
    return {
        "version": "1",
        "$schema_id": "chapter-placement",
        "framework_ref": str(
            data.get("framework_ref") or "_chapter-framework.json",
        ).strip(),
        "themes_ref": str(data.get("themes_ref") or "_lens-themes.json").strip(),
        "chapters": chapters_out,
    }


def load_chapter_placement(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"chapter_placement file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid chapter_placement JSON: {exc}") from exc
    errors = validate_chapter_placement(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_chapter_placement(data)


def save_chapter_placement(
    path: Path,
    data: dict[str, Any],
    *,
    known_fl_ids: set[str] | None = None,
    chapter_ids: set[str] | None = None,
    fl_to_chapter: dict[str, str] | None = None,
) -> None:
    normalized = normalize_chapter_placement(data if isinstance(data, dict) else {})
    errors = validate_chapter_placement(
        normalized,
        known_fl_ids=known_fl_ids,
        chapter_ids=chapter_ids,
        fl_to_chapter=fl_to_chapter,
    )
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
