"""Load and query compose stage section upstream graph (subset of section registry)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from section_registry_schema import (
    dependency_graph_subset,
    load_section_registry,
    stable_upstream_edges,
    upstream_edges,
)


def validate_dependency_graph(data: dict[str, Any]) -> list[str]:
    """Validate dependency graph payload (registry upstream subset)."""
    from section_registry_schema import validate_section_registry

    return validate_section_registry(data)


def normalize_dependency_graph(data: dict[str, Any]) -> dict[str, Any]:
    """Return normalized dependency graph."""
    return dependency_graph_subset(data)


def dependency_graph_from_data(data: dict[str, Any]) -> dict[str, Any]:
    """Project an in-memory section-registry object to the upstream graph."""
    from section_registry_schema import registry_from_data

    return dependency_graph_subset(registry_from_data(data))


def load_dependency_graph(
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Load dependency graph from the SKILL section-registry. No arbitrary path."""
    return dependency_graph_subset(
        load_section_registry(project_root=project_root),
    )
