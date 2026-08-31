#!/usr/bin/env python3
"""Load unified compose stage section registry (order, headings, upstream graph)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[3]
_CORE = _SCRIPTS / "core"
_IO = _SCRIPTS / "io"
_INDUCTIVE = _SCRIPTS / "inductive"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
if str(_IO) not in sys.path:
    sys.path.insert(0, str(_IO))
if str(_INDUCTIVE) not in sys.path:
    sys.path.insert(0, str(_INDUCTIVE))
from workflow_paths import WORKFLOW_SCRIPTS  # noqa: E402
from kw_facets import validate_facets_list  # noqa: E402


def _ensure_workflow_scripts() -> None:
    if str(WORKFLOW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(WORKFLOW_SCRIPTS))


_RELATION_TYPES = frozenset(
    {
        "operationalize",
        "respect_exclude",
        "preserve_invariant",
        "instantiate",
        "decompose",
    }
)

_REGISTRY_SCHEME_KEY = "section-registry"
_PRESENCE_VALUES = frozenset({"required", "optional"})
_PRESENCE_DEFAULT = "required"
# Optional co-location key for Writing chapter clustering (not a lens / not coverage).
_CLUSTER_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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


def _validate_section_contract(section_key: str, contract: Any) -> list[str]:
    """Validate contract object shape for a section."""
    errors: list[str] = []
    if not isinstance(contract, dict):
        errors.append(f"sections.{section_key}.contract must be an object")
        return errors
    for key in ("required", "forbidden"):
        items = contract.get(key)
        if items is None:
            continue
        if not isinstance(items, list):
            errors.append(f"sections.{section_key}.contract.{key} must be a list when present")
            continue
        for index, item in enumerate(items):
            if not str(item).strip():
                errors.append(
                    f"sections.{section_key}.contract.{key}[{index}] must be a non-empty string"
                )
    return errors


def _effective_project_root(project_root: Path | None) -> Path:
    return (project_root or Path.cwd()).resolve()


def resolve_section_registry_path(
    project_root: Path | None = None,
    *,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
    profile_path: Path | None = None,
) -> Path:
    """Return the SKILL install path for the section-registry template."""
    root = _effective_project_root(project_root)
    _ensure_workflow_scripts()
    from compose_profile_context import get_active_profile  # noqa: WPS433
    from load_compose_template import resolve_compose_template_path  # noqa: WPS433

    pid = profile_id or get_active_profile()
    return resolve_compose_template_path(
        _REGISTRY_SCHEME_KEY,
        root,
        profile_id=pid,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
        profile_path=profile_path,
    )


def project_root_from_cycle_dir(cycle_dir: Path) -> Path:
    """Derive project root from `.cache/{platform}/lulu-dev-workflow/{cycle_id}`."""
    return cycle_dir.resolve().parent.parent.parent.parent


def registry_from_data(data: Any) -> dict[str, Any]:
    """Validate and normalize an in-memory section-registry object."""
    if not isinstance(data, dict):
        raise ValueError("section-registry must be a JSON object")
    errors = validate_section_registry(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_section_registry(data)


def fetch_section_registry(
    project_root: Path,
    *,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    """Load and validate section-registry from the SKILL install."""
    _ensure_workflow_scripts()
    from compose_profile_context import get_active_profile  # noqa: WPS433
    from load_compose_template import load_compose_template  # noqa: WPS433

    pid = profile_id or get_active_profile()
    content = load_compose_template(
        _REGISTRY_SCHEME_KEY,
        project_root.resolve(),
        profile_id=pid,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
        profile_path=profile_path,
    )
    return registry_from_data(json.loads(content))


def lens_key_sequence(data: dict[str, Any]) -> list[str]:
    """Return lens keys: ``sections`` keys when no ``section_order`` (archive-5.0).

    If ``section_order`` is present, that list is authoritative for key membership
    and upstream ordering checks. Chapter spine must not use this list (narrative arc).
    """
    sections = data.get("sections")
    order = data.get("section_order")
    if isinstance(order, list) and order:
        return [str(key).upper() for key in order]
    if isinstance(sections, dict) and sections:
        return [str(key).upper() for key in sections]
    return []


def validate_section_registry(data: dict[str, Any]) -> list[str]:
    """Validate section registry payload."""
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r} (expected '1')")

    preamble = data.get("document_preamble")
    if not isinstance(preamble, str) or not preamble.strip():
        errors.append("document_preamble must be a non-empty string")

    sections = data.get("sections")
    if not isinstance(sections, dict) or not sections:
        errors.append("sections must be a non-empty object")
        return errors

    order = data.get("section_order")
    if order is not None and (not isinstance(order, list) or not order):
        errors.append("section_order must be a non-empty list when present")
        return errors

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
        heading = str(entry.get("heading", "")).strip()
        if not heading:
            errors.append(f"sections.{key}.heading is required")
        intent = entry.get("intent")
        if intent is not None and (not isinstance(intent, str) or not intent.strip()):
            errors.append(f"sections.{key}.intent must be a non-empty string when present")
        desc = entry.get("desc")
        if desc is not None and (not isinstance(desc, str) or not desc.strip()):
            errors.append(f"sections.{key}.desc must be a non-empty string when present")
        intent_boundary = entry.get("intent_boundary")
        if intent_boundary is not None and (
            not isinstance(intent_boundary, str) or not intent_boundary.strip()
        ):
            errors.append(
                f"sections.{key}.intent_boundary must be a non-empty string when present"
            )
        presence = entry.get("presence")
        if presence is not None and presence not in _PRESENCE_VALUES:
            errors.append(
                f"sections.{key}.presence must be one of {sorted(_PRESENCE_VALUES)} "
                f"(got {presence!r})"
            )
        cluster = entry.get("cluster")
        if cluster is not None:
            if not isinstance(cluster, str) or not cluster.strip():
                errors.append(
                    f"sections.{key}.cluster must be a non-empty string when present"
                )
            elif not _CLUSTER_RE.fullmatch(cluster.strip()):
                errors.append(
                    f"sections.{key}.cluster must match "
                    f"[a-z0-9]+(?:-[a-z0-9]+)* (got {cluster!r})"
                )
        has_intent = isinstance(intent, str) and intent.strip()
        has_desc = isinstance(desc, str) and desc.strip()
        if not has_intent and not has_desc:
            errors.append(f"sections.{key} requires intent or desc")
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
        if entry.get("guidance") is not None:
            errors.append(f"sections.{key}.guidance is not supported; use section-form-registry")
            continue
        if entry.get("contract") is not None:
            errors.append(f"sections.{key}.contract is not supported; use section-form-registry")
            continue
        if "facets" in entry:
            try:
                validate_facets_list(entry.get("facets"), lens=key)
            except ValueError as exc:
                errors.append(str(exc))

    if isinstance(order, list) and order:
        for key in sections:
            if str(key).upper() not in order_keys:
                errors.append(f"sections.{key} is not listed in section_order")

    return errors


def normalize_section_registry(data: dict[str, Any]) -> dict[str, Any]:
    """Return normalized section registry."""
    keep_order = isinstance(data.get("section_order"), list) and bool(data.get("section_order"))
    order = lens_key_sequence(data)
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
        normalized: dict[str, Any] = {
            "heading": str(entry.get("heading", "")).strip(),
            "aliases": aliases,
            "upstream": upstream,
            "relations": relations,
        }
        intent = entry.get("intent")
        if isinstance(intent, str) and intent.strip():
            normalized["intent"] = intent.strip()
        desc = entry.get("desc")
        if isinstance(desc, str) and desc.strip():
            normalized["desc"] = desc.strip()
        elif "intent" in normalized:
            normalized["desc"] = normalized["intent"]
        intent_boundary = entry.get("intent_boundary")
        if isinstance(intent_boundary, str) and intent_boundary.strip():
            normalized["intent_boundary"] = intent_boundary.strip()
        presence = entry.get("presence")
        normalized["presence"] = presence if presence in _PRESENCE_VALUES else _PRESENCE_DEFAULT
        cluster = entry.get("cluster")
        if isinstance(cluster, str) and cluster.strip():
            normalized["cluster"] = cluster.strip()
        if "facets" in entry:
            # Validated upstream; normalize to string[] facet seeds.
            normalized["facets"] = validate_facets_list(
                entry.get("facets"), lens=key
            )
        sections[key] = normalized
    out: dict[str, Any] = {
        "version": "1",
        "document_preamble": str(data.get("document_preamble", "")),
        "sections": sections,
    }
    if keep_order:
        out["section_order"] = order
    return out


def load_section_registry(
    *,
    project_root: Path | None = None,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    """Load section-registry from the SKILL install. No arbitrary path."""
    return fetch_section_registry(
        _effective_project_root(project_root),
        profile_id=profile_id,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
        profile_path=profile_path,
    )


@lru_cache(maxsize=8)
def _registry_for_path(path_str: str) -> dict[str, Any]:
    return registry_from_data(json.loads(Path(path_str).read_text(encoding="utf-8")))


def _active_registry(project_root: Path | None = None) -> dict[str, Any]:
    return _registry_for_path(str(resolve_section_registry_path(project_root)))


def section_order(project_root: Path | None = None) -> tuple[str, ...]:
    """Return lens key sequence (legacy name; not document chapter spine)."""
    registry = _active_registry(project_root)
    return tuple(lens_key_sequence(registry))


def summary_section_key(project_root: Path | None = None) -> str:
    """Return section key used for tech-doc summary extraction (GO when present)."""
    order = section_order(project_root)
    if "GO" in order:
        return "GO"
    if "GOAL" in order:
        return "GOAL"
    return order[0]


def section_intent_boundary(section_key: str, project_root: Path | None = None) -> str:
    """Return intent_boundary for a section when present."""
    key = normalize_section(section_key, project_root=project_root)
    boundary = _active_registry(project_root)["sections"][key].get("intent_boundary")
    if isinstance(boundary, str):
        return boundary.strip()
    return ""


def section_keys(project_root: Path | None = None) -> frozenset[str]:
    """Return valid section keys."""
    return frozenset(section_order(project_root))


def section_headings(project_root: Path | None = None) -> dict[str, str]:
    """Return section_key → H2 heading map."""
    registry = _active_registry(project_root)
    return {
        key: registry["sections"][key]["heading"]
        for key in lens_key_sequence(registry)
    }


def section_presence_map(project_root: Path | None = None) -> dict[str, str]:
    """Return section_key -> presence ('required'|'optional', default 'required').

    Design rationale (source repo, why-only): docs/domain/ssot/compose/mechanism-ssot/compose-lens-architecture.md;
    process how archive: docs/domain/archive/compose/archive-2.0/compose-fact-first-display-layer-design.md §3.2, §11.3
    (M3, 需求2). Feeds derive coverage helpers (``derive_triggers`` / ``true_coverage_gaps``).
    """
    registry = _active_registry(project_root)
    return {
        key: registry["sections"][key].get("presence", _PRESENCE_DEFAULT)
        for key in lens_key_sequence(registry)
    }


def section_cluster_map(project_root: Path | None = None) -> dict[str, str]:
    """Return section_key -> cluster slug for lenses that declare ``cluster``.

    Display/Writing co-location hint only — not a completeness obligation and not a
    ``lens_tags`` value. See archive-3.0 compose-design-stability-lenses-cluster-design.
    """
    registry = _active_registry(project_root)
    out: dict[str, str] = {}
    for key in lens_key_sequence(registry):
        cluster = registry["sections"][key].get("cluster")
        if isinstance(cluster, str) and cluster.strip():
            out[key] = cluster.strip()
    return out


def section_aliases(project_root: Path | None = None) -> dict[str, str]:
    """Return normalized alias → section_key map."""
    registry = _active_registry(project_root)
    aliases: dict[str, str] = {}
    for key in lens_key_sequence(registry):
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


def section_intent_text(section_key: str, project_root: Path | None = None) -> str:
    """Return intent substance text for a section (intent field, else desc)."""
    key = normalize_section(section_key, project_root=project_root)
    entry = _active_registry(project_root)["sections"][key]
    intent = entry.get("intent")
    if isinstance(intent, str) and intent.strip():
        return intent.strip()
    return str(entry.get("desc", "")).strip()


def section_guidance(section_key: str, project_root: Path | None = None) -> str:
    """Return form guidance for a section when present."""
    from section_form_registry_schema import section_form_guidance  # noqa: WPS433

    return section_form_guidance(section_key, project_root=project_root)


def section_contract(section_key: str, project_root: Path | None = None) -> dict[str, list[str]]:
    """Return normalized contract for a section when present."""
    from section_form_registry_schema import section_form_contract  # noqa: WPS433

    return section_form_contract(section_key, project_root=project_root)


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
    parser = argparse.ArgumentParser(description="Compose stage section registry utilities")
    parser.add_argument("--path", type=Path, help="Override registry JSON path")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=".",
        help="Project root for template cache resolution",
    )
    parser.add_argument("--document-preamble", action="store_true", help="Print preamble markdown")
    parser.add_argument("--normalize", metavar="SECTION", help="Normalize section to key")
    parser.add_argument(
        "--section-intent",
        metavar="SECTION",
        help="Print intent text for section (intent field, else desc)",
    )
    parser.add_argument(
        "--section-intent-boundary",
        metavar="SECTION",
        help="Print intent_boundary for section",
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
    parser.add_argument("--schema", action="store_true", help="Print loaded registry JSON")
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()

    try:
        registry = (
            registry_from_data(json.loads(args.path.read_text(encoding="utf-8")))
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

    if args.section_intent:
        try:
            print(section_intent_text(args.section_intent, project_root=project_root))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    if args.section_intent_boundary:
        try:
            print(section_intent_boundary(args.section_intent_boundary, project_root=project_root))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    if args.section_guidance:
        try:
            print(section_guidance(args.section_guidance, project_root=project_root))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    if args.section_contract:
        try:
            json.dump(
                section_contract(args.section_contract, project_root=project_root),
                sys.stdout,
                indent=2,
                ensure_ascii=False,
            )
            sys.stdout.write("\n")
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
