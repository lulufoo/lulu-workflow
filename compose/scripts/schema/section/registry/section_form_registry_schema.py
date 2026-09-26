#!/usr/bin/env python3
"""Load compose stage section form registry (writing cognition per section key).

Hard format only (no legacy guidance/contract path):
  { reading_axis: str,  # key required; empty string temporarily allowed
    presentation: { guidance, allowed[{carrier,structure,when}], forbidden },
    expression: { required, forbidden } }

CLI:
    python3 section_form_registry_schema.py --schema
    python3 section_form_registry_schema.py --dump --path <form.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

_SCHEMA_DIR = Path(__file__).resolve().parent
_SCRIPTS = _SCHEMA_DIR.parents[3]
_KERNEL = _SCRIPTS / "_kernel"
_TEMPLATES = _SCRIPTS / "templates"
for _p in (_KERNEL, _TEMPLATES):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from workflow_paths import WORKFLOW_SCRIPTS  # noqa: E402

from section_registry_schema import (  # noqa: E402
    _normalize_contract,
    _validate_section_contract,
)

SCHEMA_ID = "section-form-schema"
_FORM_SCHEME_KEY = "section-form-registry"

_SCHEMA: list[dict[str, Any]] = [
    {"field": "version", "type": "string", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "$schema_id", "type": "string", "required": False,
     "description": "Fixed value: section-form-schema when present"},
    {"field": "profile_id", "type": "string", "required": False,
     "description": "Optional compose profile label when present"},
    {"field": "section_order", "type": "list[string]", "required": False,
     "description": "Optional; when omitted, lens keys = sections object key order (archive-5.0)"},
    {"field": "sections", "type": "object", "required": True,
     "description": "section_key → { reading_axis, presentation, expression }"},
]

_FORBIDDEN_SECTION_KEYS = frozenset(
    {
        "heading",
        "aliases",
        "upstream",
        "relations",
        "intent",
        "desc",
        "intent_boundary",
    }
)


def get_schema() -> list[dict[str, Any]]:
    """Return field definitions for section form registry JSON."""
    return list(_SCHEMA)


def _ensure_workflow_scripts() -> None:
    if str(WORKFLOW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(WORKFLOW_SCRIPTS))


def _effective_project_root(project_root: Path | None) -> Path:
    return (project_root or Path.cwd()).resolve()


def validate_section_form_alignment(
    form: dict[str, Any],
    intent_registry: dict[str, Any],
) -> list[str]:
    """Ensure form lens keys match section-registry exactly."""
    from section_registry_schema import lens_key_sequence

    errors: list[str] = []
    intent_order = lens_key_sequence(intent_registry)
    form_order = lens_key_sequence(form)
    if intent_order != form_order:
        errors.append(
            "lens key sequence must match section-registry exactly "
            f"(intent={intent_order!r}, form={form_order!r})"
        )
    intent_keys = set(intent_order)
    for key in form_order:
        if key not in intent_keys:
            errors.append(f"sections.{key} not listed in section-registry lens keys")
    return errors


def _validate_allowed_entry(key: str, idx: int, item: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        errors.append(f"sections.{key}.presentation.allowed[{idx}] must be an object")
        return errors
    carrier = item.get("carrier")
    structure = item.get("structure")
    when = item.get("when")
    if not isinstance(carrier, str) or not carrier.strip():
        errors.append(f"sections.{key}.presentation.allowed[{idx}].carrier must be a non-empty string")
    if not isinstance(structure, str) or not structure.strip():
        errors.append(f"sections.{key}.presentation.allowed[{idx}].structure must be a non-empty string")
    if not isinstance(when, str) or not when.strip():
        errors.append(f"sections.{key}.presentation.allowed[{idx}].when must be a non-empty string")
    return errors


def _validate_presentation_entry(key: str, entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if "reading_axis" not in entry:
        errors.append(f"sections.{key}.reading_axis is required")
    else:
        axis = entry.get("reading_axis")
        if not isinstance(axis, str):
            errors.append(f"sections.{key}.reading_axis must be a string")
    presentation = entry.get("presentation")
    expression = entry.get("expression")
    if not isinstance(presentation, dict):
        errors.append(f"sections.{key}.presentation must be an object")
        return errors
    guidance = presentation.get("guidance")
    if not isinstance(guidance, str) or not guidance.strip():
        errors.append(f"sections.{key}.presentation.guidance must be a non-empty string")
    allowed = presentation.get("allowed")
    if not isinstance(allowed, list):
        errors.append(f"sections.{key}.presentation.allowed must be a list")
    else:
        for idx, item in enumerate(allowed):
            errors.extend(_validate_allowed_entry(key, idx, item))
    forbidden = presentation.get("forbidden")
    if forbidden is not None:
        if not isinstance(forbidden, list):
            errors.append(f"sections.{key}.presentation.forbidden must be a list when present")
        else:
            for idx, item in enumerate(forbidden):
                if not isinstance(item, str):
                    errors.append(f"sections.{key}.presentation.forbidden[{idx}] must be a string")
    if expression is not None:
        errors.extend(_validate_section_contract(key, expression))
    return errors


def validate_section_form_registry(data: dict[str, Any]) -> list[str]:
    """Validate section form registry payload."""
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r} (expected '1')")

    schema_id = data.get("$schema_id")
    if schema_id is not None and schema_id != SCHEMA_ID:
        errors.append(f"$schema_id must be {SCHEMA_ID!r} when present")

    sections = data.get("sections")
    if not isinstance(sections, dict) or not sections:
        errors.append("sections must be a non-empty object")
        return errors

    order = data.get("section_order")
    if order is not None and (not isinstance(order, list) or not order):
        errors.append("section_order must be a non-empty list when present")
        return errors

    from section_registry_schema import lens_key_sequence

    order_keys = lens_key_sequence(data)
    if not order_keys:
        errors.append("sections must declare at least one lens key")
        return errors
    if len(order_keys) != len(set(order_keys)):
        errors.append("lens key list contains duplicate keys")

    for key in order_keys:
        entry = sections.get(key)
        if not isinstance(entry, dict):
            errors.append(f"sections.{key} must be an object")
            continue
        for forbidden in _FORBIDDEN_SECTION_KEYS:
            if forbidden in entry:
                errors.append(f"sections.{key}.{forbidden} is not supported")
        if "guidance" in entry or "contract" in entry:
            errors.append(
                f"sections.{key} legacy guidance/contract format is not supported; "
                "use reading_axis + presentation + expression"
            )
            continue
        if "presentation" not in entry:
            errors.append(f"sections.{key}.presentation is required")
            continue
        errors.extend(_validate_presentation_entry(key, entry))

    for key in sections:
        if str(key).upper() not in order_keys:
            errors.append(f"sections.{key} is not listed in section_order")

    return errors


def normalize_section_form_registry(data: dict[str, Any]) -> dict[str, Any]:
    """Return normalized section form registry."""
    from section_registry_schema import lens_key_sequence

    keep_order = isinstance(data.get("section_order"), list) and bool(data.get("section_order"))
    order = lens_key_sequence(data)
    sections_raw = data.get("sections") or {}
    sections: dict[str, dict[str, Any]] = {}
    for key in order:
        entry = dict(sections_raw.get(key) or {})
        normalized: dict[str, Any] = {}
        axis = entry.get("reading_axis")
        if isinstance(axis, str):
            normalized["reading_axis"] = axis.strip()
        elif "reading_axis" in entry:
            normalized["reading_axis"] = ""
        pres = entry.get("presentation")
        if isinstance(pres, dict):
            normalized_pres: dict[str, Any] = {}
            guidance = pres.get("guidance")
            if isinstance(guidance, str) and guidance.strip():
                normalized_pres["guidance"] = guidance.strip()
            allowed = pres.get("allowed")
            if isinstance(allowed, list):
                rows: list[dict[str, str]] = []
                for a in allowed:
                    if not isinstance(a, dict):
                        continue
                    rows.append(
                        {
                            "carrier": str(a.get("carrier", "")).strip(),
                            "structure": str(a.get("structure", "")).strip(),
                            "when": str(a.get("when", "")).strip(),
                        }
                    )
                normalized_pres["allowed"] = rows
            forbidden = pres.get("forbidden")
            if isinstance(forbidden, list):
                normalized_pres["forbidden"] = [
                    str(f).strip() for f in forbidden if isinstance(f, str) and str(f).strip()
                ]
            normalized["presentation"] = normalized_pres
        normalized["expression"] = _normalize_contract(entry.get("expression"))
        sections[key] = normalized
    result: dict[str, Any] = {
        "version": "1",
        "sections": sections,
    }
    if keep_order:
        result["section_order"] = order
    if data.get("profile_id"):
        result["profile_id"] = str(data["profile_id"]).strip()
    if data.get("$schema_id"):
        result["$schema_id"] = str(data["$schema_id"]).strip()
    return result


def merge_section_form_into_registry(
    intent_registry: dict[str, Any],
    form_registry: dict[str, Any],
) -> dict[str, Any]:
    """Return intent registry copy with form fields merged from form registry."""
    from section_registry_schema import lens_key_sequence

    merged = json.loads(json.dumps(intent_registry))
    for key in lens_key_sequence(merged):
        form_entry = form_registry["sections"].get(key) or {}
        section = merged["sections"][key]
        if "reading_axis" in form_entry:
            section["reading_axis"] = form_entry["reading_axis"]
        if form_entry.get("presentation"):
            section["presentation"] = form_entry["presentation"]
            section["expression"] = form_entry.get("expression", {"required": [], "forbidden": []})
    return merged


def resolve_section_form_registry_path(
    project_root: Path | None = None,
    *,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
    profile_path: Path | None = None,
) -> Path | None:
    """Return a direct form template path, or None when the role is omitted."""
    root = _effective_project_root(project_root)
    _ensure_workflow_scripts()
    from compose_profile_context import get_active_profile  # noqa: WPS433
    from compose_template_loader import (  # noqa: WPS433
        ComposeTemplateLoadError,
        resolve_compose_template_path,
    )

    pid = profile_id or get_active_profile()
    try:
        return resolve_compose_template_path(
            _FORM_SCHEME_KEY,
            root,
            profile_id=pid,
            cycle_id=cycle_id,
            conversation_id=conversation_id,
            profile_path=profile_path,
        )
    except ComposeTemplateLoadError:
        return None


def form_registry_from_data(
    data: Any,
    *,
    intent_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and normalize an in-memory section-form-registry object."""
    if not isinstance(data, dict):
        raise ValueError("section-form-registry must be a JSON object")
    errors = validate_section_form_registry(data)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = normalize_section_form_registry(data)
    if intent_registry is not None:
        errors = validate_section_form_alignment(normalized, intent_registry)
        if errors:
            raise ValueError("; ".join(errors))
    return normalized


def fetch_section_form_registry(
    project_root: Path,
    *,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    """Load and validate section-form-registry from the SKILL install."""
    _ensure_workflow_scripts()
    from compose_profile_context import get_active_profile  # noqa: WPS433
    from compose_template_loader import load_compose_template  # noqa: WPS433
    from section_registry_schema import fetch_section_registry  # noqa: WPS433

    pid = profile_id or get_active_profile()
    content = load_compose_template(
        _FORM_SCHEME_KEY,
        project_root.resolve(),
        profile_id=pid,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
        profile_path=profile_path,
    )
    data = json.loads(content)
    intent_registry = fetch_section_registry(
        project_root,
        profile_id=pid,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
        profile_path=profile_path,
    )
    return form_registry_from_data(data, intent_registry=intent_registry)


def load_section_form_registry(
    *,
    project_root: Path | None = None,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    """Load section-form-registry from the SKILL install. No arbitrary path."""
    return fetch_section_form_registry(
        _effective_project_root(project_root),
        profile_id=profile_id,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
        profile_path=profile_path,
    )


@lru_cache(maxsize=8)
def _form_registry_for_path(path_str: str) -> dict[str, Any]:
    return form_registry_from_data(json.loads(Path(path_str).read_text(encoding="utf-8")))


def _optional_form_registry(project_root: Path | None = None) -> dict[str, Any] | None:
    path = resolve_section_form_registry_path(project_root)
    if path is None:
        return None
    return _form_registry_for_path(str(path))


def section_form_guidance(section_key: str, project_root: Path | None = None) -> str:
    """Return form guidance for a section when present."""
    from section_registry_schema import normalize_section  # noqa: WPS433

    key = normalize_section(section_key, project_root=project_root)
    form = _optional_form_registry(project_root)
    if not form:
        return ""
    entry = form["sections"].get(key, {})
    # Current format
    pres = entry.get("presentation")
    if isinstance(pres, dict):
        guidance = pres.get("guidance")
        if isinstance(guidance, str):
            return guidance.strip()
        return ""
    # Legacy format
    guidance = entry.get("guidance")
    if isinstance(guidance, str):
        return guidance.strip()
    return ""


def section_form_contract(
    section_key: str,
    project_root: Path | None = None,
) -> dict[str, list[str]]:
    """Return normalized expression/contract for a section when present."""
    from section_registry_schema import normalize_section  # noqa: WPS433

    key = normalize_section(section_key, project_root=project_root)
    form = _optional_form_registry(project_root)
    if not form:
        return {"required": [], "forbidden": []}
    entry = form["sections"].get(key, {})
    # Current format
    if "expression" in entry:
        return _normalize_contract(entry["expression"])
    # Legacy format
    contract = entry.get("contract")
    if contract is not None:
        return _normalize_contract(contract)
    return {"required": [], "forbidden": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compose stage section form registry utilities")
    parser.add_argument("--path", type=Path, help="Override form registry JSON path")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=".",
        help="Project root for template cache resolution",
    )
    parser.add_argument("--schema", action="store_true", help="Print field schema JSON")
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Print loaded and normalized form registry JSON",
    )
    parser.add_argument(
        "--section-guidance",
        metavar="SECTION",
        help="Print guidance for section when present",
    )
    parser.add_argument(
        "--section-contract",
        metavar="SECTION",
        help="Print contract JSON for section when present",
    )
    args = parser.parse_args(argv)

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    try:
        registry = (
            form_registry_from_data(json.loads(args.path.read_text(encoding="utf-8")))
            if args.path
            else load_section_form_registry(project_root=args.project_root.resolve())
        )
    except (OSError, ValueError, json.JSONDecodeError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.section_guidance:
        try:
            print(section_form_guidance(args.section_guidance, project_root=args.project_root))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    if args.section_contract:
        try:
            json.dump(
                section_form_contract(args.section_contract, project_root=args.project_root),
                sys.stdout,
                indent=2,
                ensure_ascii=False,
            )
            sys.stdout.write("\n")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    if not args.dump:
        parser.print_help()
        return 0

    json.dump(registry, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
