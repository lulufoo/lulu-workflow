#!/usr/bin/env python3
"""Schema and I/O for revision ``discussion-pointer.json`` (multi-subdesign v1.1).

On-disk shape (exact keys only — no legacy field compatibility)::

    {
      "tree_ref": {"path": "dependency-tree.json", "version": 1},
      "focus": "L1",
      "by_id": {
        "L1": {"intake": "pending"|"done", "acceptance": "pending"|"done"},
        ...
      }
    }

Maturity keys (noun phases + pending|done):
  - ``intake`` — Drafting Step 0 producer closed (Inductive or Deductive
    complete); EnterPolicy admits a node when every dependency is
    ``intake: done``. Not Split intake slots.
  - ``acceptance`` — L evaluated / production exit closed; StageGate and
    assemble-index require dependency or all-node ``acceptance: done``.

``dependency-tree.json`` may still carry ``order[]`` as a node inventory / topo
listing — it is not a push constraint (EnterPolicy / StageGate decide admission).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dependency_tree_schema import DEPENDENCY_TREE_FILENAME

DISCUSSION_POINTER_FILENAME = "discussion-pointer.json"
_MATURITY = frozenset({"pending", "done"})
_BY_ID_KEYS = frozenset({"intake", "acceptance"})
_ON_DISK_KEYS = frozenset({"tree_ref", "focus", "by_id"})
_FORBIDDEN_LEGACY_KEYS = frozenset({"pointer", "frontier", "phase"})


def discussion_pointer_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / DISCUSSION_POINTER_FILENAME


def active_slice_dir(revision_dir: Path) -> Path:
    """Return ``revision/Lx`` when a discussion pointer exists; else revision root.

    Revisions without ``discussion-pointer.json`` use the revision root
    (single-slice layout). Multi-L work requires a valid v1.1 pointer file.
    """
    rev = Path(revision_dir).resolve()
    path = discussion_pointer_path(rev)
    if not path.is_file():
        return rev
    data = load_discussion_pointer(rev)
    return (rev / str(data["focus"])).resolve()


def build_pointer_from_tree(tree: dict[str, Any]) -> dict[str, Any]:
    order = list(tree.get("order") or [])
    if not order:
        raise ValueError("tree.order must be non-empty")
    first = order[0]
    by_id = {
        nid: {"intake": "pending", "acceptance": "pending"} for nid in order
    }
    return {
        "tree_ref": {
            "path": DEPENDENCY_TREE_FILENAME,
            "version": int(tree.get("version", 1)),
        },
        "focus": first,
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

    legacy = sorted(set(pointer) & _FORBIDDEN_LEGACY_KEYS)
    if legacy:
        errors.append(
            "v1.0 keys forbidden (no compatibility): "
            + ", ".join(legacy)
            + "; expected only tree_ref|focus|by_id"
        )

    extra = set(pointer) - _ON_DISK_KEYS
    if extra:
        errors.append(f"unexpected keys: {sorted(extra)}")

    tree_ref = pointer.get("tree_ref")
    if not isinstance(tree_ref, dict):
        errors.append("tree_ref must be an object")
    else:
        if str(tree_ref.get("path", "")) != DEPENDENCY_TREE_FILENAME:
            errors.append(f"tree_ref.path must be {DEPENDENCY_TREE_FILENAME!r}")
        if tree_ref.get("version") != tree.get("version"):
            errors.append("tree_ref.version must match dependency-tree version")

    focus = str(pointer.get("focus", "")).strip()
    if not focus:
        errors.append("focus is required")
    elif focus not in id_set:
        errors.append(f"focus unknown id {focus!r}")

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
            errors.append(f"{where} must have keys intake|acceptance only")
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
    if not isinstance(pointer, dict):
        raise ValueError("pointer must be an object")
    payload = {
        "tree_ref": pointer.get("tree_ref"),
        "focus": str(pointer.get("focus", "")).strip(),
        "by_id": pointer.get("by_id"),
    }
    errors = validate_discussion_pointer(payload, tree)
    if errors:
        raise ValueError("; ".join(errors))
    path = discussion_pointer_path(revision_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
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
    return {
        "tree_ref": data["tree_ref"],
        "focus": str(data["focus"]).strip(),
        "by_id": data["by_id"],
    }


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


def can_admit(
    tree: dict[str, Any],
    pointer: dict[str, Any],
    node_id: str,
) -> tuple[bool, str | None]:
    """EnterPolicy: admit when every dependency has ``intake: done``."""
    order = list(tree.get("order") or [])
    if node_id not in order:
        return False, f"unknown node id {node_id!r}"
    by_id = pointer.get("by_id") or {}
    incomplete = [
        dep
        for dep in deps_of(tree, node_id)
        if (by_id.get(dep) or {}).get("intake") != "done"
    ]
    if incomplete:
        return (
            False,
            f"EnterPolicy: deps not intake=done: {', '.join(incomplete)}",
        )
    return True, None


def can_enter_evaluate(
    tree: dict[str, Any],
    pointer: dict[str, Any],
    node_id: str,
) -> tuple[bool, str | None]:
    """StageGate: enter Evaluating when every dependency has ``acceptance: done``."""
    order = list(tree.get("order") or [])
    if node_id not in order:
        return False, f"unknown node id {node_id!r}"
    by_id = pointer.get("by_id") or {}
    incomplete = [
        dep
        for dep in deps_of(tree, node_id)
        if (by_id.get(dep) or {}).get("acceptance") != "done"
    ]
    if incomplete:
        return (
            False,
            f"StageGate: deps not acceptance=done: {', '.join(incomplete)}",
        )
    return True, None


def ready_ids(tree: dict[str, Any], pointer: dict[str, Any]) -> list[str]:
    """Nodes that pass EnterPolicy (DAG-ready), in tree.order inventory order."""
    out: list[str] = []
    for nid in list(tree.get("order") or []):
        ok, _ = can_admit(tree, pointer, nid)
        if ok:
            out.append(nid)
    return out


def active_ids(pointer: dict[str, Any]) -> list[str]:
    """Session-active set: current focus only (single-focus v1.1)."""
    focus = str(pointer.get("focus", "")).strip()
    return [focus] if focus else []


def focus_phase(pointer: dict[str, Any], node_id: str | None = None) -> str:
    """Advisory work-mode: intake until that L's intake is done, else acceptance."""
    nid = node_id or str(pointer.get("focus", "")).strip()
    cell = (pointer.get("by_id") or {}).get(nid) or {}
    if cell.get("intake") != "done":
        return "intake"
    return "acceptance"


def slice_past_init(revision_dir: Path, node_id: str) -> bool:
    """True when the L slice looks past Init (has narrative arc or design doc)."""
    d = Path(revision_dir) / node_id
    return (d / "_narrative-arc.json").is_file() or (d / "design-doc.md").is_file()
