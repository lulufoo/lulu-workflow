#!/usr/bin/env python3
"""Schema/I/O for process ``_narrative-arc.draft.json`` (archive-9.0 T1/T2).

Process how: docs/domain/archive/compose/archive-9.0/
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

DRAFT_BASENAME = "_narrative-arc.draft.json"
DRAFT_KIND = "narrative-arc-draft"
_STATUS = "draft"
_FACT_ID_RE = re.compile(r"^F-\d+$")
_MOUNT_VALUES = frozenset({"seed", "deepen", "add"})


def narrative_arc_draft_path(revision_or_slice_dir: Path) -> Path:
    return Path(revision_or_slice_dir) / DRAFT_BASENAME


def empty_draft(*, note: str = "", source: str = "post-g1-auto") -> dict[str, Any]:
    return {
        "version": "1",
        "kind": DRAFT_KIND,
        "status": _STATUS,
        "tree": {"id": "root", "title": "Narrative axis", "children": []},
        "leaves": [],
        "unresolved": [],
        "meta": {
            "leaf_mounts": {},
            "note": note,
            "source": source,
        },
    }


def validate_narrative_arc_draft(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["draft root must be an object"]
    if str(data.get("version", "")).strip() != "1":
        errors.append("draft.version must be '1'")
    if str(data.get("kind", "")).strip() != DRAFT_KIND:
        errors.append(f"draft.kind must be {DRAFT_KIND!r}")
    if str(data.get("status", "")).strip() != _STATUS:
        errors.append("draft.status must be 'draft'")

    leaves = data.get("leaves")
    if not isinstance(leaves, list) or not leaves:
        errors.append("draft.leaves must be a non-empty array")
        return errors

    seen: set[str] = set()
    fact_owner: dict[str, str] = {}
    for index, leaf in enumerate(leaves):
        prefix = f"leaves[{index}]"
        if not isinstance(leaf, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if leaf.get("chapters") is not None:
            errors.append(f"{prefix}.chapters must not be present on draft")
        leaf_id = str(leaf.get("id", "")).strip()
        if not leaf_id:
            errors.append(f"{prefix}.id must be non-empty")
        elif leaf_id in seen:
            errors.append(f"{prefix}.id duplicate: {leaf_id!r}")
        else:
            seen.add(leaf_id)
        if not str(leaf.get("title", "")).strip():
            errors.append(f"{prefix}.title must be non-empty")
        raw_ids = leaf.get("fact_ids")
        if raw_ids is None:
            raw_ids = []
        if not isinstance(raw_ids, list):
            errors.append(f"{prefix}.fact_ids must be an array")
            continue
        for j, fid in enumerate(raw_ids):
            fid_s = str(fid).strip()
            if not _FACT_ID_RE.match(fid_s):
                errors.append(f"{prefix}.fact_ids[{j}] must match F-<n>")
                continue
            if fid_s in fact_owner:
                errors.append(
                    f"fact {fid_s!r} mapped to multiple leaves: "
                    f"{fact_owner[fid_s]!r} and {leaf_id!r}",
                )
            else:
                fact_owner[fid_s] = leaf_id

    meta = data.get("meta")
    if meta is not None and not isinstance(meta, dict):
        errors.append("draft.meta must be an object when present")
    elif isinstance(meta, dict):
        mounts = meta.get("leaf_mounts")
        if mounts is not None:
            if not isinstance(mounts, dict):
                errors.append("meta.leaf_mounts must be an object")
            else:
                for lid, mount in mounts.items():
                    if str(mount).strip() not in _MOUNT_VALUES:
                        errors.append(
                            f"meta.leaf_mounts[{lid!r}] must be seed|deepen|add",
                        )
                    if str(lid).strip() and str(lid).strip() not in seen:
                        errors.append(
                            f"meta.leaf_mounts unknown leaf {lid!r}",
                        )

    if "tree" in data and data.get("tree") is not None:
        if not isinstance(data.get("tree"), (dict, list)):
            errors.append("draft.tree must be an object or array when present")

    return errors


def normalize_narrative_arc_draft(data: dict[str, Any]) -> dict[str, Any]:
    leaves_out: list[dict[str, Any]] = []
    for leaf in data.get("leaves") or []:
        if not isinstance(leaf, dict):
            continue
        leaves_out.append(
            {
                "id": str(leaf.get("id", "")).strip(),
                "title": str(leaf.get("title", "")).strip(),
                "fact_ids": [
                    str(x).strip()
                    for x in (leaf.get("fact_ids") or [])
                    if str(x).strip()
                ],
            }
        )
    meta_in = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    mounts = meta_in.get("leaf_mounts") if isinstance(meta_in.get("leaf_mounts"), dict) else {}
    leaf_mounts = {
        str(k).strip(): str(v).strip()
        for k, v in mounts.items()
        if str(k).strip() and str(v).strip() in _MOUNT_VALUES
    }
    for leaf in leaves_out:
        leaf_mounts.setdefault(leaf["id"], "seed")
    out: dict[str, Any] = {
        "version": "1",
        "kind": DRAFT_KIND,
        "status": _STATUS,
        "leaves": leaves_out,
        "meta": {
            "leaf_mounts": leaf_mounts,
            "note": str(meta_in.get("note") or ""),
            "source": str(meta_in.get("source") or "post-g1-auto"),
        },
    }
    if "tree" in data and data.get("tree") is not None:
        out["tree"] = data["tree"]
    for bucket in ("excluded", "unresolved"):
        raw = data.get(bucket)
        if isinstance(raw, list):
            out[bucket] = raw
    if "open_items" in meta_in:
        out["meta"]["open_items"] = meta_in.get("open_items")
    return out


def load_narrative_arc_draft(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"narrative arc draft not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid draft JSON: {exc}") from exc
    errors = validate_narrative_arc_draft(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_narrative_arc_draft(data)


def save_narrative_arc_draft(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_narrative_arc_draft(data if isinstance(data, dict) else {})
    errors = validate_narrative_arc_draft(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized


def _find_node(node: Any, node_id: str) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    if str(node.get("id", "")).strip() == node_id:
        return node
    for child in node.get("children") or []:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None


def _ensure_children(node: dict[str, Any]) -> list[Any]:
    children = node.get("children")
    if not isinstance(children, list):
        children = []
        node["children"] = children
    return children


def add_leaf_node(
    data: dict[str, Any],
    *,
    parent_id: str,
    leaf_id: str,
    title: str,
    index: int | None = None,
) -> dict[str, Any]:
    draft = deepcopy(normalize_narrative_arc_draft(data))
    if any(str(leaf.get("id")) == leaf_id for leaf in draft["leaves"]):
        raise ValueError(f"leaf id already exists: {leaf_id!r}")
    tree = draft.get("tree")
    if not isinstance(tree, dict):
        tree = {"id": "root", "title": "Narrative axis", "children": []}
        draft["tree"] = tree
    parent = _find_node(tree, parent_id)
    if parent is None:
        raise ValueError(f"parent not found: {parent_id!r}")
    children = _ensure_children(parent)
    entry = {"id": leaf_id, "title": title, "children": []}
    if index is None:
        children.append(entry)
    else:
        if index < 0 or index > len(children):
            raise ValueError(f"index out of range: {index}")
        children.insert(index, entry)
    draft["leaves"].append({"id": leaf_id, "title": title, "fact_ids": []})
    draft["meta"]["leaf_mounts"][leaf_id] = "add"
    return draft


def rename_leaf(data: dict[str, Any], *, leaf_id: str, title: str) -> dict[str, Any]:
    draft = deepcopy(normalize_narrative_arc_draft(data))
    title = title.strip()
    if not title:
        raise ValueError("title must be non-empty")
    found = False
    for leaf in draft["leaves"]:
        if leaf["id"] == leaf_id:
            leaf["title"] = title
            found = True
            break
    if not found:
        raise ValueError(f"leaf not found: {leaf_id!r}")
    tree = draft.get("tree")
    node = _find_node(tree, leaf_id) if isinstance(tree, dict) else None
    if node is not None:
        node["title"] = title
    return draft


def deepen_leaf(
    data: dict[str, Any],
    *,
    leaf_id: str,
    note: str | None = None,
) -> dict[str, Any]:
    draft = deepcopy(normalize_narrative_arc_draft(data))
    if not any(leaf["id"] == leaf_id for leaf in draft["leaves"]):
        raise ValueError(f"leaf not found: {leaf_id!r}")
    mounts = draft["meta"]["leaf_mounts"]
    if mounts.get(leaf_id) == "seed":
        mounts[leaf_id] = "deepen"
    if note is not None:
        draft["meta"]["note"] = note
    return draft


def attach_fact(
    data: dict[str, Any],
    *,
    leaf_id: str,
    fact_id: str,
) -> dict[str, Any]:
    draft = deepcopy(normalize_narrative_arc_draft(data))
    fid = fact_id.strip()
    if not _FACT_ID_RE.match(fid):
        raise ValueError(f"fact id must match F-<n>: {fact_id!r}")
    for leaf in draft["leaves"]:
        if fid in leaf["fact_ids"] and leaf["id"] != leaf_id:
            raise ValueError(
                f"fact {fid!r} already attached to {leaf['id']!r}",
            )
    target = None
    for leaf in draft["leaves"]:
        if leaf["id"] == leaf_id:
            target = leaf
            break
    if target is None:
        raise ValueError(f"leaf not found: {leaf_id!r}")
    if fid not in target["fact_ids"]:
        target["fact_ids"].append(fid)
    return draft


def _remove_from_parent(tree: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    children = tree.get("children")
    if not isinstance(children, list):
        return None
    for i, child in enumerate(children):
        if not isinstance(child, dict):
            continue
        if str(child.get("id", "")).strip() == node_id:
            return children.pop(i)
        found = _remove_from_parent(child, node_id)
        if found is not None:
            return found
    return None


def move_node(
    data: dict[str, Any],
    *,
    node_id: str,
    new_parent: str,
    index: int | None = None,
) -> dict[str, Any]:
    draft = deepcopy(normalize_narrative_arc_draft(data))
    tree = draft.get("tree")
    if not isinstance(tree, dict):
        raise ValueError("draft.tree missing")
    if node_id == new_parent:
        raise ValueError("cannot move node under itself")
    detached = _remove_from_parent(tree, node_id)
    if detached is None:
        raise ValueError(f"node not found in tree: {node_id!r}")
    parent = _find_node(tree, new_parent)
    if parent is None:
        raise ValueError(f"new_parent not found: {new_parent!r}")
    if _find_node(detached, new_parent) is not None:
        raise ValueError("cannot move node under its descendant")
    children = _ensure_children(parent)
    if index is None:
        children.append(detached)
    else:
        if index < 0 or index > len(children):
            raise ValueError(f"index out of range: {index}")
        children.insert(index, detached)
    return draft
