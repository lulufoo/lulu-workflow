"""Load and query tech-plan section upstream graph (subset of section registry)."""

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


def load_dependency_graph(
    path: Path | None = None,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Load dependency graph from section registry template."""
    return dependency_graph_subset(
        load_section_registry(path, project_root=project_root),
    )
