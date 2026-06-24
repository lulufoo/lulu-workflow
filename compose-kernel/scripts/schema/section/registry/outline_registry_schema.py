#!/usr/bin/env python3
"""Load compose stage outline registry (presentation blocks → intent keys).

CLI:
    python3 outline_registry_schema.py --schema
    python3 outline_registry_schema.py --dump --path <outline.json>
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

SCHEMA_ID = "outline-schema"
_OUTLINE_SCHEME_KEY = "outline-registry"

_SCHEMA: list[dict[str, Any]] = [
    {"field": "version", "type": "string", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "$schema_id", "type": "string", "required": False,
     "description": "Fixed value: outline-schema when present"},
    {"field": "cycle_type", "type": "string", "required": False,
     "description": "Optional cycle-type label when present"},
    {"field": "outline_order", "type": "list[string]", "required": True,
     "description": "Ordered block keys for document assembly"},
    {"field": "blocks", "type": "object", "required": True,
     "description": "block_key → { heading, intents[], guidance?, contract?, assembly? }"},
]


def _normalize_contract(raw: Any) -> dict[str, list[str]]:
    """Return normalized contract with required/forbidden string lists."""
    if not isinstance(raw, dict):
        return {"required": [], "forbidden": []}
    result: dict[str, list[str]] = {}
    for key in ("required", "forbidden"):
        items = raw.get(key)
        if not isinstance(items, list):
            result[key] = []
            continue
        result[key] = [
            str(item).strip()
            for item in items
            if str(item).strip()
        ]
    return result


def _validate_block_contract(block_key: str, contract: Any) -> list[str]:
    """Validate contract object shape for a block."""
    errors: list[str] = []
    if not isinstance(contract, dict):
        errors.append(f"blocks.{block_key}.contract must be an object")
        return errors
    for key in ("required", "forbidden"):
        items = contract.get(key)
        if items is None:
            continue
        if not isinstance(items, list):
            errors.append(f"blocks.{block_key}.contract.{key} must be a list when present")
            continue
        for index, item in enumerate(items):
            if not str(item).strip():
                errors.append(
                    f"blocks.{block_key}.contract.{key}[{index}] must be a non-empty string"
                )
    return errors


def _normalize_assembly(raw: Any) -> dict[str, list[str]]:
    """Return normalized assembly with transitions/forbidden string lists."""
    if not isinstance(raw, dict):
        return {"transitions": [], "forbidden": []}
    result: dict[str, list[str]] = {}
    for key in ("transitions", "forbidden"):
        items = raw.get(key)
        if not isinstance(items, list):
            result[key] = []
            continue
        result[key] = [
            str(item).strip()
            for item in items
            if str(item).strip()
        ]
    return result


def _validate_block_assembly(block_key: str, assembly: Any) -> list[str]:
    """Validate assembly object shape for a block."""
    errors: list[str] = []
    if not isinstance(assembly, dict):
        errors.append(f"blocks.{block_key}.assembly must be an object")
        return errors
    for key in ("transitions", "forbidden"):
        items = assembly.get(key)
        if items is None:
            continue
        if not isinstance(items, list):
            errors.append(f"blocks.{block_key}.assembly.{key} must be a list when present")
            continue
        for index, item in enumerate(items):
            if not str(item).strip():
                errors.append(
                    f"blocks.{block_key}.assembly.{key}[{index}] must be a non-empty string"
                )
    return errors


def get_schema() -> list[dict[str, Any]]:
    """Return field definitions for outline registry JSON."""
    return list(_SCHEMA)


def _ensure_workflow_scripts() -> None:
    if str(WORKFLOW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(WORKFLOW_SCRIPTS))


def _effective_project_root(project_root: Path | None) -> Path:
    return (project_root or Path.cwd()).resolve()


def resolve_outline_registry_path(project_root: Path | None = None) -> Path:
    """Return fetched outline template cache path; fetch when cache is empty."""
    root = _effective_project_root(project_root)
    _ensure_workflow_scripts()
    from compose_template_registry import framework_section, resolve_config_key  # noqa: WPS433
    from fetch_template import cache_path  # noqa: WPS433
    from subagent_config import detect_platform  # noqa: WPS433

    section = framework_section()
    config_key = resolve_config_key(_OUTLINE_SCHEME_KEY)
    cached = cache_path(root, detect_platform(), section, config_key)
    if cached.exists() and cached.read_text(encoding="utf-8").strip():
        return cached
    fetch_outline_registry(root)
    if cached.exists() and cached.read_text(encoding="utf-8").strip():
        return cached
    raise FileNotFoundError(
        f"outline registry cache not available after fetch: {cached}. "
        "Run: python3 fetch_compose_framework.py --role outline-registry --project-root ."
    )


def fetch_outline_registry(
    project_root: Path,
    *,
    platform: str | None = None,
    force: bool = False,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Fetch outline registry via workflow-config template URL."""
    _ensure_workflow_scripts()
    from compose_profile_context import get_active_profile  # noqa: WPS433
    from fetch_compose_framework import fetch_compose_framework  # noqa: WPS433
    from section_registry_schema import fetch_section_registry  # noqa: WPS433

    pid = profile_id or get_active_profile()
    content = fetch_compose_framework(
        _OUTLINE_SCHEME_KEY,
        project_root.resolve(),
        platform=platform,
        force=force,
        profile_id=pid,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
    )
    data = json.loads(content)
    errors = validate_outline_registry(data)
    if errors:
        raise ValueError("; ".join(errors))
    section_registry = fetch_section_registry(
        project_root,
        platform=platform,
        force=False,
        profile_id=pid,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
    )
    errors = validate_outline_section_alignment(data, section_registry)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_outline_registry(data)


def validate_outline_section_alignment(
    outline: dict[str, Any],
    section_registry: dict[str, Any],
) -> list[str]:
    """Ensure outline intents match section_order exactly."""
    errors: list[str] = []
    section_order = [
        str(key).upper() for key in (section_registry.get("section_order") or [])
    ]
    outline_intents: set[str] = set()
    for block_key in outline.get("outline_order") or []:
        block = (outline.get("blocks") or {}).get(block_key) or {}
        for intent in block.get("intents") or []:
            outline_intents.add(str(intent).upper())

    section_set = set(section_order)
    for key in section_set:
        if key not in outline_intents:
            errors.append(
                f"section_order key {key!r} missing from outline blocks intents",
            )
    for intent in sorted(outline_intents):
        if intent not in section_set:
            errors.append(f"outline intent {intent!r} not listed in section_order")
    return errors


def validate_outline_registry(data: dict[str, Any]) -> list[str]:
    """Validate outline registry payload."""
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r} (expected '1')")

    schema_id = data.get("$schema_id")
    if schema_id is not None and schema_id != SCHEMA_ID:
        errors.append(f"$schema_id must be {SCHEMA_ID!r} when present")

    order = data.get("outline_order")
    if not isinstance(order, list) or not order:
        errors.append("outline_order must be a non-empty list")
        return errors

    blocks = data.get("blocks")
    if not isinstance(blocks, dict):
        errors.append("blocks must be an object")
        return errors

    order_keys = [str(key).upper() for key in order]
    if len(order_keys) != len(set(order_keys)):
        errors.append("outline_order contains duplicate keys")

    if data.get("document_preamble_addon") is not None:
        errors.append("document_preamble_addon is not supported")

    seen_intents: set[str] = set()
    for key in order_keys:
        entry = blocks.get(key)
        if not isinstance(entry, dict):
            errors.append(f"blocks.{key} must be an object")
            continue
        heading = str(entry.get("heading", "")).strip()
        if not heading:
            errors.append(f"blocks.{key}.heading is required")
        intents = entry.get("intents")
        if not isinstance(intents, list) or not intents:
            errors.append(f"blocks.{key}.intents must be a non-empty list")
            continue
        for raw_intent in intents:
            intent_key = str(raw_intent).upper()
            if not intent_key:
                errors.append(f"blocks.{key}.intents contains empty key")
                continue
            if intent_key in seen_intents:
                errors.append(
                    f"intent {intent_key!r} appears in more than one outline block"
                )
            seen_intents.add(intent_key)
        guidance = entry.get("guidance")
        if entry.get("reader_note") is not None:
            errors.append(f"blocks.{key}.reader_note is not supported")
            continue
        has_guidance = isinstance(guidance, str) and guidance.strip()
        contract = entry.get("contract")
        assembly = entry.get("assembly")
        has_assembly = assembly is not None
        if has_guidance:
            if contract is None:
                errors.append(f"blocks.{key}.contract is required when guidance is present")
            else:
                errors.extend(_validate_block_contract(key, contract))
        elif contract is not None:
            errors.append(
                f"blocks.{key}.contract without guidance is not supported; "
                "use sections.{key}.contract or omit both for assembly-only blocks"
            )
        if has_assembly:
            errors.extend(_validate_block_assembly(key, assembly))

    for key in blocks:
        if str(key).upper() not in order_keys:
            errors.append(f"blocks.{key} is not listed in outline_order")

    return errors


def normalize_outline_registry(data: dict[str, Any]) -> dict[str, Any]:
    """Return normalized outline registry."""
    order = [str(key).upper() for key in data["outline_order"]]
    blocks_raw = data.get("blocks") or {}
    blocks: dict[str, dict[str, Any]] = {}
    for key in order:
        entry = dict(blocks_raw.get(key) or {})
        intents = [str(item).upper() for item in entry.get("intents") or [] if str(item).strip()]
        normalized: dict[str, Any] = {
            "heading": str(entry.get("heading", "")).strip(),
            "intents": intents,
        }
        guidance = entry.get("guidance")
        if isinstance(guidance, str) and guidance.strip():
            normalized["guidance"] = guidance.strip()
            normalized["contract"] = _normalize_contract(entry.get("contract"))
        assembly = entry.get("assembly")
        if isinstance(assembly, dict):
            normalized_assembly = _normalize_assembly(assembly)
            if normalized_assembly["transitions"] or normalized_assembly["forbidden"]:
                normalized["assembly"] = normalized_assembly
        blocks[key] = normalized
    result: dict[str, Any] = {
        "version": "1",
        "outline_order": order,
        "blocks": blocks,
    }
    if data.get("cycle_type"):
        result["cycle_type"] = str(data["cycle_type"]).strip()
    if data.get("$schema_id"):
        result["$schema_id"] = str(data["$schema_id"]).strip()
    return result


def load_outline_registry(
    path: Path | None = None,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Load outline registry from explicit path or fetch cache."""
    target = path or resolve_outline_registry_path(project_root)
    if not target.exists():
        raise FileNotFoundError(f"outline registry not found: {target}")
    data = json.loads(target.read_text(encoding="utf-8"))
    errors = validate_outline_registry(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_outline_registry(data)


@lru_cache(maxsize=8)
def _outline_for_path(path_str: str) -> dict[str, Any]:
    return load_outline_registry(Path(path_str))


def _active_outline(project_root: Path | None = None) -> dict[str, Any]:
    return _outline_for_path(str(resolve_outline_registry_path(project_root)))


def outline_order(project_root: Path | None = None) -> tuple[str, ...]:
    """Return ordered outline block keys."""
    return tuple(_active_outline(project_root)["outline_order"])


def outline_intent_map(project_root: Path | None = None) -> dict[str, str]:
    """Return intent_key → outline_block_key map."""
    registry = _active_outline(project_root)
    mapping: dict[str, str] = {}
    for block_key in registry["outline_order"]:
        for intent_key in registry["blocks"][block_key]["intents"]:
            mapping[intent_key] = block_key
    return mapping


def outline_block_assembly(
    section_key: str,
    project_root: Path | None = None,
) -> dict[str, list[str]]:
    """Return normalized assembly for the block containing section_key."""
    key = str(section_key).strip().upper()
    registry = _active_outline(project_root)
    block_key = outline_intent_map(project_root).get(key)
    if not block_key:
        return {"transitions": [], "forbidden": []}
    assembly = registry["blocks"][block_key].get("assembly")
    if isinstance(assembly, dict):
        return _normalize_assembly(assembly)
    return {"transitions": [], "forbidden": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compose stage outline registry utilities")
    parser.add_argument("--path", type=Path, help="Override outline JSON path")
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
        help="Print loaded and normalized outline registry JSON",
    )
    args = parser.parse_args(argv)

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    if not args.dump:
        parser.print_help()
        return 0

    project_root = args.project_root.resolve()

    try:
        registry = (
            load_outline_registry(args.path)
            if args.path
            else load_outline_registry(project_root=project_root)
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    json.dump(registry, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
