#!/usr/bin/env python3
"""Temporary C-node Split candidates and confirmed D-node projections."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

_DECISION_SCRIPTS = Path(__file__).resolve().parents[3] / "decision" / "scripts"
if str(_DECISION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DECISION_SCRIPTS))

from dec_io import atomic_write_text  # noqa: E402

CANDIDATE_VERSION = 1
_C_ID_RE = re.compile(r"^C[1-9]\d*$")
_D_ID_RE = re.compile(r"^D\d+$")
_NODE_KEYS = frozenset({"id", "title", "summary"})
_EDGE_KEYS = frozenset({"from", "to"})
_RULER_KEYS = frozenset({"id", "job", "boundary", "deps_summary"})
_MAPPING_KEYS = frozenset({"kind", "node_id"})


def _transaction_id(value: object) -> str:
    transaction_id = str(value).strip()
    if not transaction_id or Path(transaction_id).name != transaction_id:
        raise ValueError("candidate transaction_id must be a single path component")
    return transaction_id


def candidate_path(approach_root: Path, transaction_id: str) -> Path:
    """Return a transaction-scoped candidate path under the approach root."""
    return (
        Path(approach_root).resolve()
        / "mainline-reopen"
        / _transaction_id(transaction_id)
        / "candidate.json"
    )


def _require_candidate_id(value: object, *, where: str) -> str:
    node_id = str(value).strip()
    if not _C_ID_RE.match(node_id):
        raise ValueError(f"{where} must match C<number>, got {node_id!r}")
    return node_id


def _validate_candidate(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("split candidate must be an object")
    if data.get("version") != CANDIDATE_VERSION:
        raise ValueError(f"split candidate version must be {CANDIDATE_VERSION}")
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("split candidate nodes must be a non-empty list")
    normalized_nodes: list[dict[str, str]] = []
    ids: list[str] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or set(node) - _NODE_KEYS:
            raise ValueError(f"split candidate nodes[{index}] has invalid keys")
        node_id = _require_candidate_id(node.get("id"), where=f"nodes[{index}].id")
        if node_id in ids:
            raise ValueError(f"split candidate duplicate node id {node_id!r}")
        title = str(node.get("title", "")).strip()
        summary = str(node.get("summary", "")).strip()
        if not title or not summary:
            raise ValueError(f"split candidate nodes[{index}] title and summary are required")
        ids.append(node_id)
        normalized_nodes.append({"id": node_id, "title": title, "summary": summary})
    id_set = set(ids)

    edges = data.get("edges")
    if not isinstance(edges, list):
        raise ValueError("split candidate edges must be a list")
    normalized_edges: list[dict[str, str]] = []
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict) or set(edge) - _EDGE_KEYS:
            raise ValueError(f"split candidate edges[{index}] has invalid keys")
        frm = _require_candidate_id(edge.get("from"), where=f"edges[{index}].from")
        to = _require_candidate_id(edge.get("to"), where=f"edges[{index}].to")
        if frm not in id_set or to not in id_set or frm == to:
            raise ValueError(f"split candidate edges[{index}] has invalid endpoints")
        normalized_edges.append({"from": frm, "to": to})

    order_raw = data.get("order")
    if not isinstance(order_raw, list):
        raise ValueError("split candidate order must be a list")
    order = [_require_candidate_id(item, where="order item") for item in order_raw]
    if len(order) != len(ids) or set(order) != id_set:
        raise ValueError("split candidate order must cover each node exactly once")
    positions = {node_id: index for index, node_id in enumerate(order)}
    for edge in normalized_edges:
        if positions[edge["to"]] >= positions[edge["from"]]:
            raise ValueError(
                f"split candidate order inconsistent with edge {edge['from']}->{edge['to']}"
            )

    cut_axis = str(data.get("cut_axis", "")).strip()
    if not cut_axis:
        raise ValueError("split candidate cut_axis is required")
    rulers_raw = data.get("rulers")
    if not isinstance(rulers_raw, dict) or set(rulers_raw) != id_set:
        raise ValueError("split candidate rulers must cover each candidate node")
    rulers: dict[str, dict[str, str]] = {}
    for node_id in ids:
        ruler = rulers_raw[node_id]
        if not isinstance(ruler, dict) or set(ruler) - _RULER_KEYS:
            raise ValueError(f"split candidate ruler {node_id!r} has invalid keys")
        if _require_candidate_id(ruler.get("id"), where=f"rulers[{node_id}].id") != node_id:
            raise ValueError(f"split candidate ruler {node_id!r} id must match its key")
        normalized_ruler = {
            field: str(ruler.get(field, "")).strip()
            for field in ("id", "job", "boundary", "deps_summary")
        }
        if any(not value for value in normalized_ruler.values()):
            raise ValueError(f"split candidate ruler {node_id!r} has empty fields")
        rulers[node_id] = normalized_ruler

    mapping_raw = data.get("mapping")
    if not isinstance(mapping_raw, dict) or set(mapping_raw) != id_set:
        raise ValueError("split candidate mapping must cover each candidate node")
    mapping: dict[str, dict[str, str]] = {}
    mapped_ids: set[str] = set()
    for node_id in ids:
        entry = mapping_raw[node_id]
        if not isinstance(entry, dict) or set(entry) != _MAPPING_KEYS:
            raise ValueError(f"split candidate mapping {node_id!r} has invalid keys")
        kind = str(entry.get("kind", "")).strip()
        mapped = str(entry.get("node_id", "")).strip()
        if kind not in {"existing", "new"} or not _D_ID_RE.match(mapped):
            raise ValueError(f"split candidate mapping {node_id!r} is invalid")
        if mapped in mapped_ids:
            raise ValueError(f"split candidate duplicate mapped id {mapped!r}")
        mapped_ids.add(mapped)
        mapping[node_id] = {"kind": kind, "node_id": mapped}

    return {
        "version": CANDIDATE_VERSION,
        "nodes": normalized_nodes,
        "edges": normalized_edges,
        "order": order,
        "cut_axis": cut_axis,
        "rulers": rulers,
        "mapping": mapping,
    }


def build_candidate(
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, str]],
    order: list[str],
    cut_axis: str,
    rulers: dict[str, dict[str, Any]],
    mapping: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Build and validate a temporary C-node candidate."""
    return _validate_candidate(
        {
            "version": CANDIDATE_VERSION,
            "nodes": nodes,
            "edges": edges,
            "order": order,
            "cut_axis": cut_axis,
            "rulers": rulers,
            "mapping": mapping,
        }
    )


def save_candidate(
    approach_root: Path, transaction_id: str, candidate: dict[str, Any]
) -> Path:
    """Atomically save one validated candidate for its transaction."""
    payload = _validate_candidate(candidate)
    path = candidate_path(approach_root, transaction_id)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def load_candidate(approach_root: Path, transaction_id: str) -> dict[str, Any]:
    """Load the validated candidate stored for one transaction."""
    path = candidate_path(approach_root, transaction_id)
    if not path.is_file():
        raise FileNotFoundError(f"split candidate not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _validate_candidate(raw)


def materialize_candidate(candidate: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project a human-confirmed candidate from temporary C IDs to final D IDs."""
    data = _validate_candidate(candidate)
    mapping = data["mapping"]
    remap = {candidate_id: entry["node_id"] for candidate_id, entry in mapping.items()}
    tree = {
        "version": 1,
        "status": "locked",
        "nodes": [
            {**node, "id": remap[node["id"]]}
            for node in data["nodes"]
        ],
        "edges": [
            {"from": remap[edge["from"]], "to": remap[edge["to"]]}
            for edge in data["edges"]
        ],
        "order": [remap[node_id] for node_id in data["order"]],
    }
    rulers = {
        "version": 1,
        "status": "locked",
        "cut_axis": data["cut_axis"],
        "rulers": {
            remap[node_id]: {**ruler, "id": remap[node_id]}
            for node_id, ruler in data["rulers"].items()
        },
    }
    return tree, rulers


def structure_signature(tree: dict[str, Any]) -> str:
    """Return the structural-only canonical hash for a final D dependency tree."""
    nodes = tree.get("nodes")
    edges = tree.get("edges")
    order = tree.get("order")
    if not isinstance(nodes, list) or not isinstance(edges, list) or not isinstance(order, list):
        raise ValueError("structure_signature requires tree nodes, edges, and order")
    node_ids = sorted(str(node.get("id", "")).strip() for node in nodes if isinstance(node, dict))
    normalized_edges = [
        {"from": frm, "to": to}
        for frm, to in sorted(
            (
                str(edge.get("from", "")).strip(),
                str(edge.get("to", "")).strip(),
            )
            for edge in edges
            if isinstance(edge, dict)
        )
    ]
    payload = {
        "node_ids": node_ids,
        "edges": normalized_edges,
        "order": [str(node_id).strip() for node_id in order],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
