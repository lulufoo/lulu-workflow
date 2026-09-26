"""Load and query compose stage section upstream graph (subset of section registry)."""

from __future__ import annotations

from typing import Any

from section_registry_schema import (  # noqa: F401
    dependency_graph_subset,
    stable_upstream_edges,
    upstream_edges,
)


def dependency_graph_from_data(data: dict[str, Any]) -> dict[str, Any]:
    """Project an in-memory section-registry object to the upstream graph."""
    from section_registry_schema import registry_from_data

    return dependency_graph_subset(registry_from_data(data))
