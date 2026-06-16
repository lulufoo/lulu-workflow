#!/usr/bin/env python3
"""Load feature tech-plan outline registry (presentation blocks → intent keys)."""

from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

_OUTLINE_KEY = "tpt_outline_registry_url"
_FETCH_SECTION = "tech-plan"


def _effective_project_root(project_root: Path | None) -> Path:
    return (project_root or Path.cwd()).resolve()


def resolve_outline_registry_path(project_root: Path | None = None) -> Path:
    """Return fetched outline template cache path; fetch when cache is empty."""
    root = _effective_project_root(project_root)
    workflow_scripts = Path(__file__).resolve().parents[2] / "scripts"
    if str(workflow_scripts) not in sys.path:
        sys.path.insert(0, str(workflow_scripts))
    from fetch_template import cache_path  # noqa: WPS433
    from subagent_config import detect_platform  # noqa: WPS433

    cached = cache_path(root, detect_platform(), _FETCH_SECTION, _OUTLINE_KEY)
    if cached.exists() and cached.read_text(encoding="utf-8").strip():
        return cached
    fetch_outline_registry(root)
    if cached.exists() and cached.read_text(encoding="utf-8").strip():
        return cached
    raise FileNotFoundError(
        f"outline registry cache not available after fetch: {cached}. "
        "Run: python3 fetch_plan_framework.py --role outline-registry --project-root ."
    )


def fetch_outline_registry(
    project_root: Path,
    *,
    platform: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Fetch outline registry via workflow-config template URL."""
    workflow_scripts = Path(__file__).resolve().parents[2] / "scripts"
    if str(workflow_scripts) not in sys.path:
        sys.path.insert(0, str(workflow_scripts))
    from fetch_plan_framework import fetch_plan_framework  # noqa: WPS433

    content = fetch_plan_framework(
        "outline-registry",
        project_root.resolve(),
        platform=platform,
        force=force,
    )
    data = json.loads(content)
    errors = validate_outline_registry(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_outline_registry(data)


def validate_outline_registry(data: dict[str, Any]) -> list[str]:
    """Validate outline registry payload."""
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r} (expected '1')")

    cycle_type = data.get("cycle_type")
    if cycle_type is not None and str(cycle_type).strip() != "feature":
        errors.append(f"cycle_type must be 'feature' when present; got {cycle_type!r}")

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

    addon = data.get("document_preamble_addon")
    if addon is not None and not isinstance(addon, str):
        errors.append("document_preamble_addon must be a string when present")

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
        reader_note = entry.get("reader_note")
        if reader_note is not None and (
            not isinstance(reader_note, str) or not reader_note.strip()
        ):
            errors.append(f"blocks.{key}.reader_note must be a non-empty string when present")

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
        reader_note = entry.get("reader_note")
        if isinstance(reader_note, str) and reader_note.strip():
            normalized["reader_note"] = reader_note.strip()
        blocks[key] = normalized
    result: dict[str, Any] = {
        "version": "1",
        "outline_order": order,
        "blocks": blocks,
    }
    if data.get("cycle_type"):
        result["cycle_type"] = str(data["cycle_type"]).strip()
    addon = data.get("document_preamble_addon")
    if isinstance(addon, str) and addon.strip():
        result["document_preamble_addon"] = addon
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tech-plan outline registry utilities")
    parser.add_argument("--path", type=Path, help="Override outline JSON path")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=".",
        help="Project root for template cache resolution",
    )
    parser.add_argument("--schema", action="store_true", help="Print loaded outline JSON")
    args = parser.parse_args(argv)

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

    if args.schema:
        json.dump(registry, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
