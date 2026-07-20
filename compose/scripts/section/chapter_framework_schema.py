#!/usr/bin/env python3
"""Schema and I/O for revision ``_chapter-framework.json`` (archive-3.0 Step 4′.B)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CHAPTER_FRAMEWORK_BASENAME = "_chapter-framework.json"
_FL_ID_RE = re.compile(r"^FL-(\d+)$")


def chapter_framework_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / CHAPTER_FRAMEWORK_BASENAME


def validate_chapter_framework(
    data: Any,
    *,
    known_fl_ids: set[str] | None = None,
    themes_by_fl_id: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["chapter_framework root must be an object"]
    if str(data.get("version", "")).strip() != "1":
        errors.append("chapter_framework.version must be '1'")
    chapters = data.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        return errors + ["chapter_framework.chapters must be a non-empty array"]

    seen_cid: set[str] = set()
    seen_fl: set[str] = set()

    for index, chapter in enumerate(chapters):
        prefix = f"chapters[{index}]"
        if not isinstance(chapter, dict):
            errors.append(f"{prefix} must be an object")
            continue
        cid = str(chapter.get("id", "")).strip()
        if not cid:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif cid in seen_cid:
            errors.append(f"{prefix}.id duplicate: {cid!r}")
        else:
            seen_cid.add(cid)

        title = chapter.get("display_title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"{prefix}.display_title must be a non-empty string")

        anchors = chapter.get("anchor_form_lens_ids")
        if not isinstance(anchors, list) or not anchors:
            errors.append(f"{prefix}.anchor_form_lens_ids must be a non-empty array")
            anchors = []
        for a_index, fl in enumerate(anchors):
            fl_s = str(fl).strip()
            if not _FL_ID_RE.match(fl_s):
                errors.append(
                    f"{prefix}.anchor_form_lens_ids[{a_index}] must match FL-<n>",
                )
                continue
            if fl_s in seen_fl:
                errors.append(f"{prefix}.anchor_form_lens_ids duplicate FL: {fl_s!r}")
            seen_fl.add(fl_s)
            if known_fl_ids is not None and fl_s not in known_fl_ids:
                errors.append(
                    f"{prefix}.anchor_form_lens_ids[{a_index}] {fl_s!r} "
                    "not in _lens-themes",
                )

        sections = chapter.get("sections")
        if not isinstance(sections, list) or not sections:
            errors.append(f"{prefix}.sections must be a non-empty array")
            continue
        sec_fls = [str(s.get("form_lens_id", "")).strip() for s in sections if isinstance(s, dict)]
        anchor_norm = [str(a).strip() for a in anchors]
        if sec_fls != anchor_norm:
            errors.append(
                f"{prefix}.sections form_lens_id order/set must match "
                "anchor_form_lens_ids",
            )
        for s_index, section in enumerate(sections):
            sprefix = f"{prefix}.sections[{s_index}]"
            if not isinstance(section, dict):
                errors.append(f"{sprefix} must be an object")
                continue
            heading = section.get("heading")
            if not isinstance(heading, str) or not heading.strip():
                errors.append(f"{sprefix}.heading must be a non-empty string")
                continue
            fl_s = str(section.get("form_lens_id", "")).strip()
            if themes_by_fl_id is not None and fl_s in themes_by_fl_id:
                theme = str(themes_by_fl_id[fl_s].get("theme", "")).strip()
                if heading.strip() != theme:
                    errors.append(
                        f"{sprefix}.heading {heading.strip()!r} must equal "
                        f"themes[{fl_s}].theme {theme!r}",
                    )

    if known_fl_ids is not None:
        missing = sorted(known_fl_ids - seen_fl)
        if missing:
            errors.append(
                f"chapter_framework missing form_lens_ids from themes: {missing}",
            )

    return errors


def normalize_chapter_framework(data: dict[str, Any]) -> dict[str, Any]:
    chapters_out = []
    for chapter in data.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        anchors = [str(a).strip() for a in (chapter.get("anchor_form_lens_ids") or [])]
        sections_in = chapter.get("sections") or []
        sections_out = []
        for index, fl in enumerate(anchors):
            heading = ""
            if index < len(sections_in) and isinstance(sections_in[index], dict):
                heading = str(sections_in[index].get("heading", "")).strip()
            sections_out.append({"form_lens_id": fl, "heading": heading})
        chapters_out.append(
            {
                "id": str(chapter.get("id", "")).strip(),
                "display_title": str(chapter.get("display_title", "")).strip(),
                "anchor_form_lens_ids": anchors,
                "sections": sections_out,
            }
        )
    return {"version": "1", "chapters": chapters_out}


def load_chapter_framework(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"chapter_framework file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid chapter_framework JSON: {exc}") from exc
    errors = validate_chapter_framework(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_chapter_framework(data)


def save_chapter_framework(
    path: Path,
    data: dict[str, Any],
    *,
    known_fl_ids: set[str] | None = None,
    themes_by_fl_id: dict[str, dict[str, Any]] | None = None,
) -> None:
    normalized = normalize_chapter_framework(data if isinstance(data, dict) else {})
    errors = validate_chapter_framework(
        normalized,
        known_fl_ids=known_fl_ids,
        themes_by_fl_id=themes_by_fl_id,
    )
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def fl_to_chapter_id(framework: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for chapter in framework.get("chapters") or []:
        cid = chapter["id"]
        for fl in chapter.get("anchor_form_lens_ids") or []:
            mapping[fl] = cid
    return mapping
