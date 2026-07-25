#!/usr/bin/env python3
"""Schema and I/O for revision ``dependency-tree.json`` (multi-subdesign v1.1).

Shape (SSOT for compose multi-L layout)::

    {
      "version": 1,
      "status": "draft" | "locked",
      "nodes": [{"id": "L1", "title": "...", "summary": "..."}],
      "edges": [{"from": "L2", "to": "L1"}],   # from depends on to
      "order": ["L1", "L2"]   # node inventory / topo listing — NOT a push constraint
    }

Node progress lives in ``discussion-pointer.json`` (``focus`` / ``by_id``).
Admission uses DAG EnterPolicy / StageGate, not ``order`` serial advance.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEPENDENCY_TREE_FILENAME = "dependency-tree.json"
TREE_VERSION = 1
_VALID_STATUS = frozenset({"draft", "locked"})
_NODE_ID_RE = re.compile(r"^L\d+$")
_NODE_KEYS = frozenset({"id", "title", "summary"})
_EDGE_KEYS = frozenset({"from", "to"})


def dependency_tree_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / DEPENDENCY_TREE_FILENAME


def build_tree(
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, str]],
    order: list[str],
    status: str = "draft",
    version: int = TREE_VERSION,
) -> dict[str, Any]:
    return {
        "version": int(version),
        "status": str(status),
        "nodes": [dict(n) for n in nodes],
        "edges": [dict(e) for e in edges],
        "order": list(order),
    }


def validate_dependency_tree(tree: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(tree, dict):
        return ["tree must be an object"]

    version = tree.get("version")
    if version != TREE_VERSION:
        errors.append(f"version must be {TREE_VERSION}")

    status = tree.get("status")
    if status not in _VALID_STATUS:
        errors.append("status must be draft|locked")

    nodes = tree.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        errors.append("nodes must be a non-empty list")
        return errors

    ids: list[str] = []
    seen: set[str] = set()
    for idx, node in enumerate(nodes):
        where = f"nodes[{idx}]"
        if not isinstance(node, dict):
            errors.append(f"{where} must be an object")
            continue
        extra = set(node) - _NODE_KEYS
        if extra:
            errors.append(f"{where} has unexpected keys: {sorted(extra)}")
        nid = str(node.get("id", "")).strip()
        if not _NODE_ID_RE.match(nid):
            errors.append(f"{where}.id must match L<number> (got {nid!r})")
        elif nid in seen:
            errors.append(f"duplicate node id {nid!r}")
        else:
            seen.add(nid)
            ids.append(nid)
        if not str(node.get("title", "")).strip():
            errors.append(f"{where}.title must be non-empty")
        if not str(node.get("summary", "")).strip():
            errors.append(f"{where}.summary must be non-empty")

    id_set = set(ids)
    edges = tree.get("edges")
    if not isinstance(edges, list):
        errors.append("edges must be a list")
        edges = []
    for idx, edge in enumerate(edges):
        where = f"edges[{idx}]"
        if not isinstance(edge, dict):
            errors.append(f"{where} must be an object")
            continue
        extra = set(edge) - _EDGE_KEYS
        if extra:
            errors.append(f"{where} has unexpected keys: {sorted(extra)}")
        frm = str(edge.get("from", "")).strip()
        to = str(edge.get("to", "")).strip()
        if frm not in id_set:
            errors.append(f"{where}.from unknown id {frm!r}")
        if to not in id_set:
            errors.append(f"{where}.to unknown id {to!r}")
        if frm and to and frm == to:
            errors.append(f"{where} must not be self-loop")

    order = tree.get("order")
    if not isinstance(order, list):
        errors.append("order must be a list")
        return errors
    if sorted(order) != sorted(ids) or len(order) != len(ids):
        errors.append("order must cover each node id exactly once")
    else:
        pos = {nid: i for i, nid in enumerate(order)}
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            frm = str(edge.get("from", "")).strip()
            to = str(edge.get("to", "")).strip()
            if frm in pos and to in pos and pos[to] >= pos[frm]:
                errors.append(
                    f"order inconsistent with edge {frm}->{to}: "
                    f"dependency {to!r} must precede {frm!r}"
                )

    return errors


def save_dependency_tree(revision_dir: Path, tree: dict[str, Any]) -> Path:
    errors = validate_dependency_tree(tree)
    if errors:
        raise ValueError("; ".join(errors))
    path = dependency_tree_path(revision_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tree, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_dependency_tree(revision_dir: Path) -> dict[str, Any]:
    path = dependency_tree_path(revision_dir)
    if not path.is_file():
        raise FileNotFoundError(f"missing dependency tree: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_dependency_tree(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data
