#!/usr/bin/env python3
"""Schema and I/O for revision ``discussion-pointer.json`` (multi-subdesign).

On-disk shape (exact keys only — no legacy field compatibility)::

    {
      "tree_ref": {"path": "dependency-tree.json", "version": 1},
      "focus": "L1",
      "by_id": {
        "L1": {
          "intake": "pending"|"done",
          "acceptance": "pending"|"done",
          "phase": "pending"|"in_progress"|"evaluating"|"accepted"
        },
        ...
      }
    }

Maturity + sub-state:
  - ``intake`` — producer (Inductive|Deductive) closed; EnterPolicy deps.
  - ``acceptance`` — L eval exit closed; StageGate / deliver gate deps.
  - ``phase`` — per-L sub-state machine (MUST NOT appear at pointer root;
    root ``phase`` remains a forbidden v1.0 key).

``dependency-tree.json`` ``order[]`` is inventory / topo listing, not a push
constraint (EnterPolicy / StageGate decide admission).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dependency_tree_schema import DEPENDENCY_TREE_FILENAME

DISCUSSION_POINTER_FILENAME = "discussion-pointer.json"
_MATURITY = frozenset({"pending", "done"})
_PHASES = frozenset({"pending", "in_progress", "evaluating", "accepted"})
_BY_ID_KEYS = frozenset({"intake", "acceptance", "phase"})
_ON_DISK_KEYS = frozenset({"tree_ref", "focus", "by_id"})
_FORBIDDEN_LEGACY_KEYS = frozenset({"pointer", "frontier", "phase"})


def discussion_pointer_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / DISCUSSION_POINTER_FILENAME


def empty_cell() -> dict[str, str]:
    return {"intake": "pending", "acceptance": "pending", "phase": "pending"}


def active_slice_dir(revision_dir: Path) -> Path:
    """Return ``revision/Lx`` when a discussion pointer exists; else revision root."""
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
    by_id = {nid: empty_cell() for nid in order}
    return {
        "tree_ref": {
            "path": DEPENDENCY_TREE_FILENAME,
            "version": int(tree.get("version", 1)),
        },
        "focus": first,
        "by_id": by_id,
    }


def _phase_maturity_errors(cell: dict[str, Any], where: str) -> list[str]:
    phase = cell.get("phase")
    intake = cell.get("intake")
    acceptance = cell.get("acceptance")
    errors: list[str] = []
    if phase == "pending":
        if intake != "pending" or acceptance != "pending":
            errors.append(
                f"{where}: phase=pending requires intake=pending and "
                "acceptance=pending"
            )
    elif phase == "in_progress":
        if acceptance != "pending":
            errors.append(f"{where}: phase=in_progress requires acceptance=pending")
    elif phase == "evaluating":
        if intake != "done" or acceptance != "pending":
            errors.append(
                f"{where}: phase=evaluating requires intake=done and "
                "acceptance=pending"
            )
    elif phase == "accepted":
        if intake != "done" or acceptance != "done":
            errors.append(
                f"{where}: phase=accepted requires intake=done and "
                "acceptance=done"
            )
    return errors


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
            errors.append(
                f"{where} must have keys intake|acceptance|phase only"
            )
            continue
        if cell.get("intake") not in _MATURITY:
            errors.append(f"{where}.intake must be pending|done")
        if cell.get("acceptance") not in _MATURITY:
            errors.append(f"{where}.acceptance must be pending|done")
        if cell.get("phase") not in _PHASES:
            errors.append(
                f"{where}.phase must be pending|in_progress|evaluating|accepted"
            )
        else:
            errors.extend(_phase_maturity_errors(cell, where))

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
    """StageGate: enter evaluating when every dependency has ``acceptance: done``."""
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
    """Session-active set: current focus only (single-focus)."""
    focus = str(pointer.get("focus", "")).strip()
    return [focus] if focus else []


def focus_phase(pointer: dict[str, Any], node_id: str | None = None) -> str:
    """Return persisted ``phase`` for focus (or ``node_id``)."""
    nid = node_id or str(pointer.get("focus", "")).strip()
    cell = (pointer.get("by_id") or {}).get(nid) or {}
    phase = str(cell.get("phase") or "").strip()
    return phase if phase in _PHASES else "pending"


def all_l_accepted(pointer: dict[str, Any]) -> bool:
    """True when every by_id cell is phase=accepted (and acceptance=done)."""
    by_id = pointer.get("by_id") or {}
    if not by_id:
        return False
    for cell in by_id.values():
        if not isinstance(cell, dict):
            return False
        if cell.get("phase") != "accepted" or cell.get("acceptance") != "done":
            return False
    return True


def suggested_next_l(
    tree: dict[str, Any],
    pointer: dict[str, Any],
    *,
    after_id: str | None = None,
) -> str | None:
    """Next EnterPolicy-ready L that is not yet accepted (tree.order)."""
    skip = str(after_id or "").strip()
    by_id = pointer.get("by_id") or {}
    for nid in list(tree.get("order") or []):
        if nid == skip:
            continue
        cell = by_id.get(nid) or {}
        if cell.get("phase") == "accepted":
            continue
        ok, _ = can_admit(tree, pointer, nid)
        if ok:
            return nid
    return None


def slice_past_init(revision_dir: Path, node_id: str) -> bool:
    """True when the L slice looks past Init (has narrative arc or design doc)."""
    d = Path(revision_dir) / node_id
    return (d / "_narrative-arc.json").is_file() or (d / "design-doc.md").is_file()
