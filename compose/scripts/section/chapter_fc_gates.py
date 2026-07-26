#!/usr/bin/env python3
"""Hard gates for Init chapter derive F/C + domain four-key provenance.

Shared by ``chapter_write_state_control.complete`` and
``init_compose_validation`` (Step 5). Flat derive: ``lens`` +
``form{carrier,structure}`` + ``expression_c[]``. Domain coverage is a
pre-Write planning checklist: joined ``expression_c`` must contain
``expression_conventions.register`` / ``.carriers`` / ``.scannability`` /
``.altitude`` substrings (aligns with domain SoT keys; not brittle
``domain.*`` labels). ``display_title`` is not gated.

Process how: docs/domain/archive/compose/archive-5.0/compose-expression-c-prewrite-planning-design.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chapter_artifact_paths import chapter_body_path, chapter_derive_path

# Provenance markers — match SKILL "from expression_conventions.<key>:" lines.
DOMAIN_MARKERS: tuple[str, ...] = (
    "expression_conventions.register",
    "expression_conventions.carriers",
    "expression_conventions.scannability",
    "expression_conventions.altitude",
)


def check_derive_fc(derive: Any) -> list[str]:
    """Return error strings when derive lacks F/C / domain provenance markers."""
    if not isinstance(derive, dict):
        return ["derive must be an object"]

    errors: list[str] = []
    form = derive.get("form")
    if not isinstance(form, dict):
        errors.append("form must be an object with carrier and structure")
    else:
        if not str(form.get("carrier", "")).strip():
            errors.append("form.carrier must be a non-empty string")
        if not str(form.get("structure", "")).strip():
            errors.append("form.structure must be a non-empty string")

    expression_c = derive.get("expression_c")
    if not isinstance(expression_c, list) or not expression_c:
        errors.append("expression_c must be a non-empty array")
        return errors

    joined_parts: list[str] = []
    for index, item in enumerate(expression_c):
        if not isinstance(item, str):
            errors.append(f"expression_c[{index}] must be a string")
            continue
        joined_parts.append(item)
    joined = "\n".join(joined_parts)
    for marker in DOMAIN_MARKERS:
        if marker not in joined:
            errors.append(f"expression_c missing marker substring {marker!r}")
    return errors


def check_chapter_write_artifacts(revision_dir: Path, cid: str) -> list[str]:
    """Full per-chapter write gate: derive file + F/C + non-empty body."""
    errors: list[str] = []
    derive_path = chapter_derive_path(revision_dir, cid)
    data: Any = None
    if not derive_path.is_file():
        errors.append(f"missing derive: {derive_path.name}")
    else:
        try:
            data = json.loads(derive_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid derive JSON: {exc}")
            data = None
        if data is not None:
            errors.extend(check_derive_fc(data))

    body = chapter_body_path(revision_dir, cid)
    if not body.is_file():
        errors.append(f"missing body: {body.name}")
    elif not body.read_text(encoding="utf-8").strip():
        errors.append(f"empty body: {body.name}")
    return errors
