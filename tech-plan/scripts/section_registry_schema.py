#!/usr/bin/env python3
"""Load unified tech-plan section registry (order, headings, upstream graph)."""

from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

_RELATION_TYPES = frozenset(
    {
        "operationalize",
        "respect_exclude",
        "preserve_invariant",
        "instantiate",
        "decompose",
    }
)

_REGISTRY_KEY = "tpt_section_registry_url"
_FETCH_SECTION = "tech-plan"


def _effective_project_root(project_root: Path | None) -> Path:
    return (project_root or Path.cwd()).resolve()


def resolve_section_registry_path(project_root: Path | None = None) -> Path:
    """Return fetched template cache path; fetch from framework when cache is empty."""
    root = _effective_project_root(project_root)
    workflow_scripts = Path(__file__).resolve().parents[2] / "scripts"
    if str(workflow_scripts) not in sys.path:
        sys.path.insert(0, str(workflow_scripts))
    from fetch_template import cache_path  # noqa: WPS433
    from subagent_config import detect_platform  # noqa: WPS433

    cached = cache_path(root, detect_platform(), _FETCH_SECTION, _REGISTRY_KEY)
    if cached.exists() and cached.read_text(encoding="utf-8").strip():
        return cached
    fetch_section_registry(root)
    if cached.exists() and cached.read_text(encoding="utf-8").strip():
        return cached
    raise FileNotFoundError(
        f"section registry cache not available after fetch: {cached}. "
        "Run: python3 fetch_plan_framework.py --role section-registry --project-root ."
    )


def project_root_from_cycle_dir(cycle_dir: Path) -> Path:
    """Derive project root from `.cache/{platform}/lulu-dev-workflow/{cycle_id}`."""
    return cycle_dir.resolve().parent.parent.parent.parent


def fetch_section_registry(
    project_root: Path,
    *,
    platform: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Fetch section registry via workflow-config template URL."""
    workflow_scripts = Path(__file__).resolve().parents[2] / "scripts"
    if str(workflow_scripts) not in sys.path:
        sys.path.insert(0, str(workflow_scripts))
    from fetch_plan_framework import fetch_plan_framework  # noqa: WPS433

    content = fetch_plan_framework(
        "section-registry",
        project_root.resolve(),
        platform=platform,
        force=force,
    )
    data = json.loads(content)
    errors = validate_section_registry(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_section_registry(data)


def validate_section_registry(data: dict[str, Any]) -> list[str]:
    """Validate section registry payload."""
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r} (expected '1')")

    order = data.get("section_order")
    if not isinstance(order, list) or not order:
        errors.append("section_order must be a non-empty list")
        return errors

    preamble = data.get("document_preamble")
    if not isinstance(preamble, str) or not preamble.strip():
        errors.append("document_preamble must be a non-empty string")

    sections = data.get("sections")
    if not isinstance(sections, dict):
        errors.append("sections must be an object")
        return errors

    order_keys = [str(key).upper() for key in order]
    if len(order_keys) != len(set(order_keys)):
        errors.append("section_order contains duplicate keys")

    for key in order_keys:
        entry = sections.get(key)
        if not isinstance(entry, dict):
            errors.append(f"sections.{key} must be an object")
            continue
        heading = str(entry.get("heading", "")).strip()
        if not heading:
            errors.append(f"sections.{key}.heading is required")
        aliases = entry.get("aliases", [])
        if aliases is not None and not isinstance(aliases, list):
            errors.append(f"sections.{key}.aliases must be a list")
        upstream = entry.get("upstream", [])
        if not isinstance(upstream, list):
            errors.append(f"sections.{key}.upstream must be a list")
            continue
        for upstream_key in upstream:
            uk = str(upstream_key).upper()
            if uk not in order_keys:
                errors.append(f"sections.{key}.upstream invalid key: {upstream_key!r}")
            if order_keys.index(uk) >= order_keys.index(key):
                errors.append(
                    f"sections.{key}.upstream must reference only earlier sections; "
                    f"got {upstream_key!r}"
                )
        relations = entry.get("relations", {})
        if relations is not None and not isinstance(relations, dict):
            errors.append(f"sections.{key}.relations must be an object")
        elif isinstance(relations, dict):
            for rel_key, rel_type in relations.items():
                ruk = str(rel_key).upper()
                if ruk not in [str(u).upper() for u in upstream]:
                    errors.append(f"sections.{key}.relations.{rel_key} not listed in upstream")
                if str(rel_type) not in _RELATION_TYPES:
                    errors.append(
                        f"sections.{key}.relations.{rel_key} invalid relation: {rel_type!r}"
                    )

    for key in sections:
        if str(key).upper() not in order_keys:
            errors.append(f"sections.{key} is not listed in section_order")

    return errors


def normalize_section_registry(data: dict[str, Any]) -> dict[str, Any]:
    """Return normalized section registry."""
    order = [str(key).upper() for key in data["section_order"]]
    sections_raw = data.get("sections") or {}
    sections: dict[str, dict[str, Any]] = {}
    for key in order:
        entry = dict(sections_raw.get(key) or {})
        aliases = [
            str(item).strip().lower()
            for item in entry.get("aliases") or []
            if str(item).strip()
        ]
        upstream = [str(item).upper() for item in entry.get("upstream") or []]
        relations_raw = entry.get("relations") or {}
        relations = {str(k).upper(): str(v) for k, v in relations_raw.items()}
        sections[key] = {
            "heading": str(entry.get("heading", "")).strip(),
            "aliases": aliases,
            "upstream": upstream,
            "relations": relations,
        }
    return {
        "version": "1",
        "section_order": order,
        "document_preamble": str(data.get("document_preamble", "")),
        "sections": sections,
    }


def load_section_registry(
    path: Path | None = None,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Load section registry from explicit path, fetch cache, or bundled template."""
    target = path or resolve_section_registry_path(project_root)
    if not target.exists():
        raise FileNotFoundError(f"section registry not found: {target}")
    data = json.loads(target.read_text(encoding="utf-8"))
    errors = validate_section_registry(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_section_registry(data)


@lru_cache(maxsize=8)
def _registry_for_path(path_str: str) -> dict[str, Any]:
    return load_section_registry(Path(path_str))


def _active_registry(project_root: Path | None = None) -> dict[str, Any]:
    return _registry_for_path(str(resolve_section_registry_path(project_root)))


def section_order(project_root: Path | None = None) -> tuple[str, ...]:
    """Return canonical section key order."""
    registry = _active_registry(project_root)
    return tuple(registry["section_order"])


def summary_section_key(project_root: Path | None = None) -> str:
    """Return section key used for tech-doc summary extraction."""
    return section_order(project_root)[0]


def section_keys(project_root: Path | None = None) -> frozenset[str]:
    """Return valid section keys."""
    return frozenset(section_order(project_root))


def section_headings(project_root: Path | None = None) -> dict[str, str]:
    """Return section_key → H2 heading map."""
    registry = _active_registry(project_root)
    return {key: registry["sections"][key]["heading"] for key in registry["section_order"]}


def section_aliases(project_root: Path | None = None) -> dict[str, str]:
    """Return normalized alias → section_key map."""
    registry = _active_registry(project_root)
    aliases: dict[str, str] = {}
    for key in registry["section_order"]:
        aliases[key] = key
        aliases[key.lower()] = key
        heading = registry["sections"][key]["heading"]
        aliases[heading.lower()] = key
        for alias in registry["sections"][key]["aliases"]:
            aliases[alias.lower()] = key
    return aliases


def normalize_section(raw: str, project_root: Path | None = None) -> str:
    """Normalize section key or heading alias to canonical section key."""
    key = section_aliases(project_root).get(raw.strip().lower())
    if not key:
        raise ValueError(f"unknown section: {raw!r}")
    return key


def section_heading(section_key: str, project_root: Path | None = None) -> str:
    """Return H2 heading for a section key."""
    key = normalize_section(section_key, project_root=project_root)
    return section_headings(project_root)[key]


def document_preamble(project_root: Path | None = None) -> str:
    """Return tech-doc preamble markdown (before first section)."""
    return _active_registry(project_root)["document_preamble"]


def initial_fill_results(project_root: Path | None = None) -> dict[str, dict[str, str]]:
    """Return empty per-section fill map keyed by heading name."""
    registry = _active_registry(project_root)
    results: dict[str, dict[str, str]] = {}
    for key in registry["section_order"]:
        heading = registry["sections"][key]["heading"]
        results[heading] = {
            "heading": f"## {heading}",
            "content": "",
            "status": "X",
        }
    return results


def dependency_graph_subset(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return upstream graph shape for dependency loaders."""
    reg = registry or _active_registry()
    sections: dict[str, dict[str, Any]] = {}
    for key in reg["section_order"]:
        entry = reg["sections"][key]
        sections[key] = {
            "upstream": list(entry["upstream"]),
            "relations": dict(entry["relations"]),
        }
    return {"version": "1", "sections": sections}


def upstream_edges(section_key: str, graph: dict[str, Any]) -> list[dict[str, str]]:
    """Return upstream edges for a section."""
    key = normalize_section(section_key)
    entry = graph["sections"][key]
    edges: list[dict[str, str]] = []
    for upstream in entry.get("upstream", []):
        relation = entry.get("relations", {}).get(upstream, "operationalize")
        edges.append({"upstream_section": upstream, "upstream_relation": relation})
    return edges


def stable_upstream_edges(
    section_key: str,
    graph: dict[str, Any],
    pointer: dict[str, Any],
) -> list[dict[str, str]]:
    """Return upstream edges whose upstream section is stable in the pointer."""
    stable: list[dict[str, str]] = []
    for edge in upstream_edges(section_key, graph):
        upstream = edge["upstream_section"]
        status = pointer["sections"][upstream]["status"]
        if status == "stable":
            stable.append(edge)
    return stable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tech-plan section registry utilities")
    parser.add_argument("--path", type=Path, help="Override registry JSON path")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=".",
        help="Project root for template cache resolution",
    )
    parser.add_argument("--document-preamble", action="store_true", help="Print preamble markdown")
    parser.add_argument("--normalize", metavar="SECTION", help="Normalize section to key")
    parser.add_argument("--schema", action="store_true", help="Print loaded registry JSON")
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()

    try:
        registry = (
            load_section_registry(args.path)
            if args.path
            else load_section_registry(project_root=project_root)
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.document_preamble:
        preamble = registry["document_preamble"]
        sys.stdout.write(preamble)
        if not preamble.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    if args.normalize:
        try:
            print(normalize_section(args.normalize, project_root=project_root))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    if args.schema:
        json.dump(registry, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
