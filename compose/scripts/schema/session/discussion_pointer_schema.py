#!/usr/bin/env python3
"""Schema and I/O for revision ``discussion-pointer.json`` (multi-subdesign MVP).

Runtime pointer state (pointer / frontier / phase / by_id). Topology lives in
``dependency-tree.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dependency_tree_schema import DEPENDENCY_TREE_FILENAME

DISCUSSION_POINTER_FILENAME = "discussion-pointer.json"
_PHASES = frozenset({"inductive", "production"})
_MATURITY = frozenset({"pending", "done"})
_BY_ID_KEYS = frozenset({"inductive", "production"})


def discussion_pointer_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / DISCUSSION_POINTER_FILENAME


def active_slice_dir(revision_dir: Path) -> Path:
    """Return ``revision/Lx`` when a discussion pointer exists; else revision root.

    Legacy revisions without ``discussion-pointer.json`` keep using the revision
    root (pre-multi-subdesign layout). Steady-state multi-L work always has a
    pointer (at least L1).
    """
    rev = Path(revision_dir).resolve()
    path = discussion_pointer_path(rev)
    if not path.is_file():
        return rev
    data = json.loads(path.read_text(encoding="utf-8"))
    pointer = str(data.get("pointer", "")).strip()
    if not pointer:
        raise ValueError(f"discussion-pointer.json missing pointer: {path}")
    return (rev / pointer).resolve()


def build_pointer_from_tree(tree: dict[str, Any]) -> dict[str, Any]:
    order = list(tree.get("order") or [])
    if not order:
        raise ValueError("tree.order must be non-empty")
    first = order[0]
    by_id = {
        nid: {"inductive": "pending", "production": "pending"} for nid in order
    }
    return {
        "tree_ref": {
            "path": DEPENDENCY_TREE_FILENAME,
            "version": int(tree.get("version", 1)),
        },
        "phase": "inductive",
        "pointer": first,
        "frontier": first,
        "by_id": by_id,
    }


def validate_discussion_pointer(
    pointer: dict[str, Any],
    tree: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(pointer, dict):
        return ["pointer must be an object"]

    order = list(tree.get("order") or [])
    id_set = set(order)
    pos = {nid: i for i, nid in enumerate(order)}

    tree_ref = pointer.get("tree_ref")
    if not isinstance(tree_ref, dict):
        errors.append("tree_ref must be an object")
    else:
        if str(tree_ref.get("path", "")) != DEPENDENCY_TREE_FILENAME:
            errors.append(f"tree_ref.path must be {DEPENDENCY_TREE_FILENAME!r}")
        if tree_ref.get("version") != tree.get("version"):
            errors.append("tree_ref.version must match dependency-tree version")

    phase = pointer.get("phase")
    if phase not in _PHASES:
        errors.append("phase must be inductive|production")

    cur = str(pointer.get("pointer", "")).strip()
    frontier = str(pointer.get("frontier", "")).strip()
    if cur not in id_set:
        errors.append(f"pointer unknown id {cur!r}")
    if frontier not in id_set:
        errors.append(f"frontier unknown id {frontier!r}")
    if cur in pos and frontier in pos and pos[cur] > pos[frontier]:
        errors.append("pointer must not advance past frontier")

    by_id = pointer.get("by_id")
    if not isinstance(by_id, dict):
        errors.append("by_id must be an object")
        return errors
    if set(by_id) != id_set:
        errors.append("by_id keys must match tree.order exactly")
    for nid, cell in by_id.items():
        where = f"by_id[{nid}]"
        if not isinstance(cell, dict):
            errors.append(f"{where} must be an object")
            continue
        if set(cell) != _BY_ID_KEYS:
            errors.append(f"{where} must have keys inductive|production only")
            continue
        for key in _BY_ID_KEYS:
            if cell.get(key) not in _MATURITY:
                errors.append(f"{where}.{key} must be pending|done")

    return errors


def save_discussion_pointer(
    revision_dir: Path,
    pointer: dict[str, Any],
    *,
    tree: dict[str, Any] | None = None,
) -> Path:
    if tree is None:
        from dependency_tree_schema import load_dependency_tree

        tree = load_dependency_tree(revision_dir)
    errors = validate_discussion_pointer(pointer, tree)
    if errors:
        raise ValueError("; ".join(errors))
    path = discussion_pointer_path(revision_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(pointer, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_discussion_pointer(revision_dir: Path) -> dict[str, Any]:
    path = discussion_pointer_path(revision_dir)
    if not path.is_file():
        raise FileNotFoundError(f"missing discussion pointer: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    from dependency_tree_schema import load_dependency_tree

    tree = load_dependency_tree(revision_dir)
    errors = validate_discussion_pointer(data, tree)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def order_index(tree: dict[str, Any], node_id: str) -> int:
    order = list(tree.get("order") or [])
    try:
        return order.index(node_id)
    except ValueError as exc:
        raise ValueError(f"unknown node id {node_id!r}") from exc


def deps_of(tree: dict[str, Any], node_id: str) -> list[str]:
    """Return ids that ``node_id`` depends on (edge.from == node_id → to)."""
    out: list[str] = []
    for edge in tree.get("edges") or []:
        if str(edge.get("from", "")) == node_id:
            out.append(str(edge.get("to", "")))
    return out
