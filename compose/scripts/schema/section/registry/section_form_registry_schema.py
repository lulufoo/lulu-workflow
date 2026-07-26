#!/usr/bin/env python3
"""Load compose stage section form registry (presentation + expression per section key).

Supports two formats (backward-compatible):
  Legacy:  { guidance: str, contract: { required, forbidden } }
  Current: { presentation: { guidance, allowed, forbidden }, expression: { required, forbidden } }

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
_CORE = _SCRIPTS / "core"
_IO = _SCRIPTS / "io"
for _p in (_CORE, _IO):
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
     "description": "section_key → { presentation, expression } (current) or { guidance, contract } (legacy)"},
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
    if not isinstance(carrier, str) or not carrier.strip():
        errors.append(f"sections.{key}.presentation.allowed[{idx}].carrier must be a non-empty string")
    if not isinstance(structure, str) or not structure.strip():
        errors.append(f"sections.{key}.presentation.allowed[{idx}].structure must be a non-empty string")
    return errors


def _validate_presentation_entry(key: str, entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    presentation = entry.get("presentation")
    expression = entry.get("expression")
    if not isinstance(presentation, dict):
        errors.append(f"sections.{key}.presentation must be an object")
        return errors
    guidance = presentation.get("guidance")
    if not isinstance(guidance, str) or not guidance.strip():
        errors.append(f"sections.{key}.presentation.guidance must be a non-empty string")
    allowed = presentation.get("allowed")
    if allowed is not None:
        if not isinstance(allowed, list):
            errors.append(f"sections.{key}.presentation.allowed must be a list when present")
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
        if "presentation" in entry:
            errors.extend(_validate_presentation_entry(key, entry))
        else:
            # Legacy format: { guidance, contract }
            guidance = entry.get("guidance")
            contract = entry.get("contract")
            has_guidance = isinstance(guidance, str) and guidance.strip()
            if guidance is not None and not has_guidance:
                errors.append(f"sections.{key}.guidance must be a non-empty string when present")
            if has_guidance:
                if contract is None:
                    errors.append(f"sections.{key}.contract is required when guidance is present")
                else:
                    errors.extend(_validate_section_contract(key, contract))
            elif contract is not None:
                errors.append(
                    f"sections.{key}.contract without guidance is not supported"
                )

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
        if "presentation" in entry:
            # Current format: { presentation, expression }
            pres = entry["presentation"]
            if isinstance(pres, dict):
                normalized_pres: dict[str, Any] = {}
                guidance = pres.get("guidance")
                if isinstance(guidance, str) and guidance.strip():
                    normalized_pres["guidance"] = guidance.strip()
                allowed = pres.get("allowed")
                if isinstance(allowed, list):
                    normalized_pres["allowed"] = [
                        {"carrier": str(a.get("carrier", "")).strip(),
                         "structure": str(a.get("structure", "")).strip()}
                        for a in allowed if isinstance(a, dict)
                    ]
                forbidden = pres.get("forbidden")
                if isinstance(forbidden, list):
                    normalized_pres["forbidden"] = [
                        str(f).strip() for f in forbidden if isinstance(f, str) and str(f).strip()
                    ]
                normalized["presentation"] = normalized_pres
            expr = entry.get("expression")
            normalized["expression"] = _normalize_contract(expr)
        else:
            # Legacy format: { guidance, contract }
            guidance = entry.get("guidance")
            if isinstance(guidance, str) and guidance.strip():
                normalized["guidance"] = guidance.strip()
                normalized["contract"] = _normalize_contract(entry.get("contract"))
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
        if form_entry.get("presentation"):
            section["presentation"] = form_entry["presentation"]
            section["expression"] = form_entry.get("expression", {"required": [], "forbidden": []})
        elif form_entry.get("guidance"):
            section["guidance"] = form_entry["guidance"]
            if form_entry.get("contract") is not None:
                section["contract"] = dict(form_entry["contract"])
    return merged


def resolve_section_form_registry_path(
    project_root: Path | None = None,
    *,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
) -> Path | None:
    """Return fetched form template cache path, or None when profile omits the role."""
    root = _effective_project_root(project_root)
    _ensure_workflow_scripts()
    from compose_profile_context import get_active_profile  # noqa: WPS433
    from compose_template_registry import (  # noqa: WPS433
        ComposeTemplateError,
        framework_section,
        resolve_config_key,
    )
    from fetch_template import cache_path  # noqa: WPS433
    from subagent_config import detect_platform  # noqa: WPS433

    pid = profile_id or get_active_profile()
    try:
        config_key = resolve_config_key(
            _FORM_SCHEME_KEY,
            pid,
            project_root=root,
            cycle_id=cycle_id,
            conversation_id=conversation_id,
        )
    except ComposeTemplateError:
        return None
    section = framework_section(
        pid,
        project_root=root,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
    )
    cached = cache_path(root, detect_platform(), section, config_key)
    if cached.exists() and cached.read_text(encoding="utf-8").strip():
        return cached
    fetch_section_form_registry(
        root,
        profile_id=pid,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
    )
    if cached.exists() and cached.read_text(encoding="utf-8").strip():
        return cached
    raise FileNotFoundError(
        f"section form registry cache not available after fetch: {cached}. "
        f"Run: python3 fetch_compose_framework.py --role section-form-registry "
        f"--profile {pid} --project-root ."
    )


def fetch_section_form_registry(
    project_root: Path,
    *,
    platform: str | None = None,
    force: bool = False,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Fetch section form registry via workflow-config template URL."""
    _ensure_workflow_scripts()
    from compose_profile_context import get_active_profile  # noqa: WPS433
    from compose_template_registry import ComposeTemplateError, resolve_config_key  # noqa: WPS433
    from fetch_compose_framework import fetch_compose_framework  # noqa: WPS433
    from section_registry_schema import fetch_section_registry  # noqa: WPS433

    pid = profile_id or get_active_profile()
    try:
        resolve_config_key(
            _FORM_SCHEME_KEY,
            pid,
            project_root=project_root.resolve(),
            cycle_id=cycle_id,
            conversation_id=conversation_id,
        )
    except ComposeTemplateError as exc:
        raise FileNotFoundError(str(exc)) from exc
    content = fetch_compose_framework(
        _FORM_SCHEME_KEY,
        project_root.resolve(),
        platform=platform,
        force=force,
        profile_id=pid,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
    )
    data = json.loads(content)
    errors = validate_section_form_registry(data)
    if errors:
        raise ValueError("; ".join(errors))
    intent_registry = fetch_section_registry(
        project_root,
        platform=platform,
        force=False,
        profile_id=pid,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
    )
    errors = validate_section_form_alignment(data, intent_registry)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_section_form_registry(data)


def load_section_form_registry(
    path: Path | None = None,
    *,
    project_root: Path | None = None,
    intent_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load section form registry from explicit path or fetch cache."""
    if path is not None:
        target = path
    else:
        resolved = resolve_section_form_registry_path(project_root)
        if resolved is None:
            raise FileNotFoundError("section form registry not configured for active profile")
        target = resolved
    if not target.exists():
        raise FileNotFoundError(f"section form registry not found: {target}")
    data = json.loads(target.read_text(encoding="utf-8"))
    errors = validate_section_form_registry(data)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = normalize_section_form_registry(data)
    if intent_registry is not None:
        errors = validate_section_form_alignment(normalized, intent_registry)
        if errors:
            raise ValueError("; ".join(errors))
    return normalized


@lru_cache(maxsize=8)
def _form_registry_for_path(path_str: str) -> dict[str, Any]:
    return load_section_form_registry(Path(path_str))


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
            load_section_form_registry(args.path)
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
