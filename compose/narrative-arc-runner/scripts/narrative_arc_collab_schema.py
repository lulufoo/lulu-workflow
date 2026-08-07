#!/usr/bin/env python3
"""Schema/I/O for collaboration display arc (archive-10.0 T3/T4).

Kind ``narrative-arc-collab``. Caller supplies the output path — never
assume Formal ``_narrative-arc.json``. Not a topic tree; no mutate APIs.

Process how: docs/domain/archive/compose/archive-10.0/
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

COLLAB_KIND = "narrative-arc-collab"
DEFAULT_COLLAB_BASENAME = "_narrative-arc.collab.json"
FORMAL_BASENAME = "_narrative-arc.json"


def default_collab_path(revision_or_slice_dir: Path) -> Path:
    return Path(revision_or_slice_dir) / DEFAULT_COLLAB_BASENAME


def assert_not_formal_path(path: Path) -> None:
    if path.name == FORMAL_BASENAME:
        raise ValueError(
            f"collab/display arc must not use Formal path ({FORMAL_BASENAME})",
        )


def empty_collab_arc(*, source: str = "narrative-arc-tool") -> dict[str, Any]:
    return {
        "version": "1",
        "kind": COLLAB_KIND,
        "status": "display",
        "tree": {"id": "root", "title": "Collaboration arc", "children": []},
        "leaves": [],
        "meta": {"leaf_mounts": {}, "note": "", "source": source},
    }


def validate_narrative_arc_collab(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["collab arc root must be an object"]
    if str(data.get("version", "")).strip() != "1":
        errors.append("collab arc version must be '1'")
    if str(data.get("kind", "")).strip() != COLLAB_KIND:
        errors.append(f"collab arc kind must be '{COLLAB_KIND}'")
    if str(data.get("status", "")).strip() != "display":
        errors.append("collab arc status must be 'display'")
    if "chapters" in data:
        errors.append("collab arc must not include chapters (Formal-only)")
    for bucket_name in ("excluded", "unresolved"):
        if bucket_name in data:
            errors.append(f"collab arc must not include {bucket_name} (Formal-only)")
    tree = data.get("tree")
    if not isinstance(tree, dict):
        errors.append("collab arc.tree must be an object")
    leaves = data.get("leaves")
    if not isinstance(leaves, list):
        errors.append("collab arc.leaves must be an array")
    else:
        for i, leaf in enumerate(leaves):
            if not isinstance(leaf, dict):
                errors.append(f"leaves[{i}] must be an object")
                continue
            if not str(leaf.get("id", "")).strip():
                errors.append(f"leaves[{i}].id required")
            if not str(leaf.get("title", "")).strip():
                errors.append(f"leaves[{i}].title required")
            fids = leaf.get("fact_ids")
            if fids is None:
                continue
            if not isinstance(fids, list):
                errors.append(f"leaves[{i}].fact_ids must be an array")
    meta = data.get("meta")
    if meta is not None and not isinstance(meta, dict):
        errors.append("collab arc.meta must be an object when present")
    return errors


def normalize_narrative_arc_collab(data: dict[str, Any]) -> dict[str, Any]:
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    leaves_out: list[dict[str, Any]] = []
    for leaf in data.get("leaves") or []:
        if not isinstance(leaf, dict):
            continue
        fids = leaf.get("fact_ids") or []
        if not isinstance(fids, list):
            fids = []
        leaves_out.append(
            {
                "id": str(leaf.get("id", "")).strip(),
                "title": str(leaf.get("title", "")).strip(),
                "fact_ids": [str(x).strip() for x in fids if str(x).strip()],
            }
        )
    tree = data.get("tree") if isinstance(data.get("tree"), dict) else {}
    return {
        "version": "1",
        "kind": COLLAB_KIND,
        "status": "display",
        "tree": tree
        or {"id": "root", "title": "Collaboration arc", "children": []},
        "leaves": leaves_out,
        "meta": {
            "leaf_mounts": dict(meta.get("leaf_mounts") or {}),
            "note": str(meta.get("note") or ""),
            "source": str(meta.get("source") or "narrative-arc-tool"),
        },
    }


def load_narrative_arc_collab(path: Path) -> dict[str, Any]:
    assert_not_formal_path(path)
    if not path.is_file():
        raise ValueError(f"collab arc not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid collab arc JSON: {exc}") from exc
    errors = validate_narrative_arc_collab(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_narrative_arc_collab(data)


def save_narrative_arc_collab(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    assert_not_formal_path(path)
    normalized = normalize_narrative_arc_collab(
        data if isinstance(data, dict) else {},
    )
    errors = validate_narrative_arc_collab(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized


def fact_node_summary(arc: dict[str, Any]) -> list[dict[str, str]]:
    """fact_id → leaf id/title summary after a collab write."""
    out: list[dict[str, str]] = []
    for leaf in arc.get("leaves") or []:
        if not isinstance(leaf, dict):
            continue
        lid = str(leaf.get("id", ""))
        title = str(leaf.get("title", ""))
        for fid in leaf.get("fact_ids") or []:
            out.append({"fact_id": str(fid), "node_id": lid, "node_title": title})
    return out


def orphan_fact_ids(
    arc: dict[str, Any],
    facts: list[dict[str, Any]],
) -> list[str]:
    attached: set[str] = set()
    for leaf in arc.get("leaves") or []:
        if not isinstance(leaf, dict):
            continue
        for fid in leaf.get("fact_ids") or []:
            attached.add(str(fid).strip())
    orphans: list[str] = []
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        fid = str(fact.get("id", "")).strip()
        if fid and fid not in attached:
            orphans.append(fid)
    return orphans


def collab_fact_coverage_errors(
    arc: dict[str, Any],
    facts: list[dict[str, Any]],
) -> list[str]:
    """Require current facts to map to exactly one collab leaf."""
    fact_ids = {
        str(fact.get("id", "")).strip()
        for fact in facts
        if isinstance(fact, dict) and str(fact.get("id", "")).strip()
    }
    owners: dict[str, str] = {}
    errors: list[str] = []
    for leaf in arc.get("leaves") or []:
        if not isinstance(leaf, dict):
            continue
        leaf_id = str(leaf.get("id", "")).strip() or "<missing>"
        for raw_id in leaf.get("fact_ids") or []:
            fact_id = str(raw_id).strip()
            if not fact_id:
                continue
            previous = owners.get(fact_id)
            if previous is not None:
                errors.append(
                    f"fact {fact_id!r} mapped to multiple collab leaves: "
                    f"{previous!r} and {leaf_id!r}",
                )
            else:
                owners[fact_id] = leaf_id

    unknown = sorted(set(owners) - fact_ids)
    if unknown:
        errors.append(f"collab arc references facts not present: {unknown}")
    unplaced = sorted(fact_ids - set(owners))
    if unplaced:
        errors.append(f"facts not placed in collab arc: {unplaced}")
    return errors


def clone_arc(data: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(data)
