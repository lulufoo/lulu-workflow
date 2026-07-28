#!/usr/bin/env python3
"""Hard gates for Init chapter derive F/C.

Shared by ``chapter_write_state_control.complete`` and
``init_compose_validation`` (Step 5). Flat derive: ``lens`` +
``form{carrier,structure}`` + non-empty ``expression[]`` (string items).
Four-key ``expression_conventions.*`` substring provenance is retired —
soft Write-time attention only (SKILL); not machine-gated here.
``display_title`` is not gated. ``expression_c`` is retired — present
key → error (use ``expression``).

F·body structure probes are data-driven
(``form_structure_body_probes.json``): load → lookup first token → run
closed-set check kinds (``contains`` / ``regex``) → format one template.
No per-structure rule branches in this module.

Process how:
docs/domain/archive/compose/archive-5.0/compose-expression-retire-checklist-and-four-key-gate-design.md
docs/domain/archive/compose/archive-5.0/compose-derive-form-expression-rename-design.md
docs/domain/archive/compose/archive-5.0/compose-body-form-structure-gate-design.md
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from chapter_artifact_paths import chapter_body_path, chapter_derive_path

_PROBE_CATALOG_PATH = Path(__file__).resolve().with_name(
    "form_structure_body_probes.json",
)
_SUPPORTED_CHECK_KINDS = frozenset({"contains", "regex"})


@lru_cache(maxsize=1)
def _load_form_structure_body_probes() -> dict[str, Any]:
    data = json.loads(_PROBE_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("form_structure_body_probes.json must be an object")
    if "error_template" not in data or "probes" not in data:
        raise ValueError(
            "form_structure_body_probes.json requires error_template and probes",
        )
    if not isinstance(data["probes"], dict):
        raise ValueError("form_structure_body_probes.json probes must be an object")
    return data


def _run_body_check(kind: str, value: str, body: str) -> bool:
    if kind == "contains":
        return value in body
    if kind == "regex":
        return re.search(value, body) is not None
    raise ValueError(f"unsupported body probe check kind: {kind!r}")


def check_body_form_structure(
    derive: Any,
    body_text: str,
    *,
    cid: str,
    body_name: str,
) -> list[str]:
    """Generic F·body probe: catalog lookup + check kinds + one template."""
    if not isinstance(derive, dict):
        return []
    form = derive.get("form")
    if not isinstance(form, dict):
        return []
    structure = str(form.get("structure", "")).strip().lower()
    if not structure:
        return []
    key = structure.split()[0]
    catalog = _load_form_structure_body_probes()
    probes = catalog["probes"]
    row = probes.get(key)
    if not isinstance(row, dict):
        return []

    checks = row.get("checks")
    if not isinstance(checks, list) or not checks:
        return [
            f"{cid}: form.structure={key} probe row has empty or invalid checks",
        ]

    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            return [
                f"{cid}: form.structure={key} checks[{index}] must be an object",
            ]
        kind = str(check.get("kind", "")).strip()
        value = check.get("value")
        if kind not in _SUPPORTED_CHECK_KINDS:
            return [
                f"{cid}: form.structure={key} unsupported check kind {kind!r}",
            ]
        if not isinstance(value, str):
            return [
                f"{cid}: form.structure={key} checks[{index}].value must be a string",
            ]
        if not _run_body_check(kind, value, body_text):
            expected = str(row.get("expected", "")).strip() or "(missing expected)"
            template = str(catalog["error_template"])
            return [
                template.format(
                    cid=cid,
                    structure_key=key,
                    expected=expected,
                    body_name=body_name,
                ),
            ]
    return []


def check_derive_fc(derive: Any) -> list[str]:
    """Return error strings when derive lacks F/C (non-empty expression)."""
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

    if "expression_c" in derive:
        errors.append(
            "expression_c is retired; use expression for the chapter C array"
        )

    expression = derive.get("expression")
    if not isinstance(expression, list) or not expression:
        errors.append("expression must be a non-empty array")
        return errors

    for index, item in enumerate(expression):
        if not isinstance(item, str):
            errors.append(f"expression[{index}] must be a string")
    return errors


def check_chapter_write_artifacts(revision_dir: Path, cid: str) -> list[str]:
    """Full per-chapter write gate: derive file + F/C + non-empty body + F·body."""
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
    body_text: str | None = None
    if not body.is_file():
        errors.append(f"missing body: {body.name}")
    else:
        body_text = body.read_text(encoding="utf-8")
        if not body_text.strip():
            errors.append(f"empty body: {body.name}")
            body_text = None

    if data is not None and body_text is not None:
        errors.extend(
            check_body_form_structure(
                data,
                body_text,
                cid=cid,
                body_name=body.name,
            ),
        )
    return errors
