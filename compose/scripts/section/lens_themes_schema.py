#!/usr/bin/env python3
"""Schema and I/O for revision ``_lens-themes.json`` (archive-3.0 Step 4′.A).

Process how: docs/domain/archive/compose/archive-3.0/compose-init-dynamic-chapter-framework-design.md
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

LENS_THEMES_BASENAME = "_lens-themes.json"
_FL_ID_RE = re.compile(r"^FL-(\d+)$")
_ENTRY_REQUIRED = ("form_lens_id", "lens_key", "theme", "desc")


def lens_themes_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / LENS_THEMES_BASENAME


def validate_lens_themes(
    data: Any,
    *,
    allowed_lenses: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["lens_themes root must be an object"]
    if str(data.get("version", "")).strip() != "1":
        errors.append("lens_themes.version must be '1'")
    entries = data.get("lens_themes")
    if not isinstance(entries, list) or not entries:
        return errors + ["lens_themes.lens_themes must be a non-empty array"]

    allowed = {l.strip().upper() for l in (allowed_lenses or []) if str(l).strip()}
    seen_fl: set[str] = set()
    seen_keys: set[str] = set()

    for index, entry in enumerate(entries):
        prefix = f"lens_themes[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in _ENTRY_REQUIRED:
            if field not in entry:
                errors.append(f"{prefix}: missing {field}")

        fl = str(entry.get("form_lens_id", "")).strip()
        if not _FL_ID_RE.match(fl):
            errors.append(f"{prefix}.form_lens_id must match FL-<n> (got {fl!r})")
        elif fl in seen_fl:
            errors.append(f"{prefix}.form_lens_id duplicate: {fl!r}")
        else:
            seen_fl.add(fl)

        key = str(entry.get("lens_key", "")).strip().upper()
        if not key:
            errors.append(f"{prefix}.lens_key must be a non-empty string")
        else:
            if key != str(entry.get("lens_key", "")).strip():
                errors.append(f"{prefix}.lens_key must be uppercase")
            if key in seen_keys:
                errors.append(f"{prefix}.lens_key duplicate: {key!r}")
            seen_keys.add(key)
            if allowed and key not in allowed:
                errors.append(
                    f"{prefix}.lens_key {key!r} not in section_order {sorted(allowed)}",
                )

        for field in ("theme", "desc"):
            val = entry.get(field)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")

    return errors


def normalize_lens_themes(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "1",
        "lens_themes": [
            {
                "form_lens_id": str(e.get("form_lens_id", "")).strip(),
                "lens_key": str(e.get("lens_key", "")).strip().upper(),
                "theme": str(e.get("theme", "")).strip(),
                "desc": str(e.get("desc", "")).strip(),
            }
            for e in (data.get("lens_themes") or [])
            if isinstance(e, dict)
        ],
    }


def load_lens_themes(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"lens_themes file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid lens_themes JSON: {exc}") from exc
    errors = validate_lens_themes(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_lens_themes(data)


def save_lens_themes(
    path: Path,
    data: dict[str, Any],
    *,
    allowed_lenses: list[str] | None = None,
) -> None:
    normalized = normalize_lens_themes(data if isinstance(data, dict) else {})
    errors = validate_lens_themes(normalized, allowed_lenses=allowed_lenses)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def themes_by_fl(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {e["form_lens_id"]: e for e in data.get("lens_themes") or []}
