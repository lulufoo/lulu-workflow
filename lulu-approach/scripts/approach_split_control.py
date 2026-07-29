#!/usr/bin/env python3
"""Approach Split structural-cut helpers (archive-1.0 P2.split).

Locked S1–S4:
  - decision-oriented minimal intake
  - lock dependency-tree + decision rulers
  - Split Delivered writes ``decision-package.slices`` with conventional
    relative paths (files may not exist yet)
  - ``Dx/`` created only on first Working focus
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_SCHEMA = _SCRIPTS / "schema"
for _p in (_SCRIPTS, _SCHEMA):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from approach_layout import (  # noqa: E402
    dx_session_dir,
    ensure_approach_layout,
)
from approach_shell_schema import load_shell, save_shell  # noqa: E402
from decision_package_schema import (  # noqa: E402
    build_decision_package,
    load_decision_package,
    save_decision_package,
)
from decision_rulers_schema import (  # noqa: E402
    build_decision_rulers,
    load_decision_rulers,
    save_decision_rulers,
    validate_decision_rulers,
)
from dependency_tree_schema import (  # noqa: E402
    build_tree,
    load_dependency_tree,
    save_dependency_tree,
    validate_dependency_tree,
)
from split_intake_schema import (  # noqa: E402
    empty_intake,
    load_split_intake,
    save_split_intake,
    validate_split_intake,
)

_DX_ID_RE = re.compile(r"^D\d+$")

CONVENTIONAL_FACT = "decision-fact.json"
CONVENTIONAL_DOC = "decision-doc.md"


def conventional_main_paths() -> dict[str, str]:
    return {
        "decision_fact_path": f"main/{CONVENTIONAL_FACT}",
        "decision_doc_path": f"main/{CONVENTIONAL_DOC}",
    }


def conventional_slice_paths(node_id: str) -> dict[str, str]:
    sid = str(node_id).strip()
    if not _DX_ID_RE.match(sid):
        raise ValueError(f"node_id must match D<number>, got {node_id!r}")
    return {
        "decision_fact_path": f"{sid}/{CONVENTIONAL_FACT}",
        "decision_doc_path": f"{sid}/{CONVENTIONAL_DOC}",
    }


def write_intake(approach_root: Path, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write / update draft intake at approach root."""
    root = Path(approach_root).resolve()
    payload = dict(data) if data is not None else empty_intake()
    payload.setdefault("version", 1)
    if "slots" not in payload:
        base = empty_intake()
        base["slots"].update(
            {k: str(v) for k, v in payload.items() if k in base["slots"]}
        )
        for meta in ("override_reason", "recommend_split"):
            if meta in payload:
                base[meta] = payload[meta]
        payload = base
    payload["status"] = "draft"
    errors = validate_split_intake(payload)
    if errors:
        raise ValueError("; ".join(errors))
    save_split_intake(root, payload)
    return payload


def complete_intake(approach_root: Path, *, confirm: bool) -> dict[str, Any]:
    """Mark intake complete (human confirm)."""
    if not confirm:
        raise ValueError("complete_intake blocked: human --confirm required")
    root = Path(approach_root).resolve()
    data = load_split_intake(root)
    data["status"] = "complete"
    errors = validate_split_intake(data)
    if errors:
        raise ValueError("; ".join(errors))
    save_split_intake(root, data)
    return data


def write_early_package(
    approach_root: Path,
    *,
    main: dict[str, str] | None = None,
    status: str = "draft",
) -> dict[str, Any]:
    """Parent Delivered early write: ``slices: []`` allowed (P0 / S4 early)."""
    root = Path(approach_root).resolve()
    ensure_approach_layout(root)
    package = build_decision_package(
        main=main or conventional_main_paths(),
        slices=[],
        status=status,
    )
    save_decision_package(root, package)
    return package


def lock_tree_and_rulers(
    approach_root: Path,
    *,
    tree: dict[str, Any],
    rulers: dict[str, Any],
    confirm: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Human-lock dependency-tree + decision rulers (S2=B). Does not mkdir Dx/."""
    if not confirm:
        raise ValueError("lock_tree_and_rulers blocked: human --confirm required")
    root = Path(approach_root).resolve()
    ensure_approach_layout(root)

    tree_payload = dict(tree)
    tree_payload.setdefault("version", 1)
    tree_payload["status"] = "locked"
    t_errors = validate_dependency_tree(tree_payload)
    if t_errors:
        raise ValueError("; ".join(t_errors))

    existing = root / "dependency-tree.json"
    if existing.is_file():
        prev = load_dependency_tree(root)
        if prev.get("status") == "locked":
            raise ValueError(
                "dependency tree already locked; re-open Split to change cut"
            )

    node_ids = [str(n["id"]) for n in tree_payload["nodes"]]
    rulers_payload = dict(rulers)
    rulers_payload.setdefault("version", 1)
    rulers_payload["status"] = "locked"
    r_errors = validate_decision_rulers(
        rulers_payload, required_node_ids=node_ids
    )
    if r_errors:
        raise ValueError("; ".join(r_errors))

    save_dependency_tree(root, tree_payload)
    save_decision_rulers(root, rulers_payload)
    return tree_payload, rulers_payload


def slices_from_locked_tree(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """Topo-ordered slices with conventional paths (files need not exist)."""
    if tree.get("status") != "locked":
        raise ValueError("slices_from_locked_tree requires status=locked")
    by_id = {str(n["id"]): n for n in tree["nodes"]}
    slices: list[dict[str, Any]] = []
    for nid in tree["order"]:
        node = by_id[str(nid)]
        paths = conventional_slice_paths(str(nid))
        slices.append(
            {
                "id": str(nid),
                "title": str(node["title"]).strip(),
                "decision_fact_path": paths["decision_fact_path"],
                "decision_doc_path": paths["decision_doc_path"],
            }
        )
    return slices


def deliver_split(
    approach_root: Path,
    *,
    tree: dict[str, Any] | None = None,
    rulers: dict[str, Any] | None = None,
    confirm: bool,
) -> dict[str, Any]:
    """Split Delivered (S4=A): lock tree+rulers, write ordered slices, mark shell.

    Does **not** create ``Dx/`` directories (S3=B).
    """
    if not confirm:
        raise ValueError("deliver_split blocked: human --confirm required")
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    if shell["macro_state"] != "Split":
        raise ValueError(
            f"deliver_split requires macro_state=Split, got {shell['macro_state']!r}"
        )

    if tree is not None and rulers is not None:
        locked_tree, _ = lock_tree_and_rulers(
            root, tree=tree, rulers=rulers, confirm=True
        )
    else:
        locked_tree = load_dependency_tree(root)
        if locked_tree.get("status") != "locked":
            raise ValueError("deliver_split blocked: dependency tree not locked")
        locked_rulers = load_decision_rulers(root)
        if locked_rulers.get("status") != "locked":
            raise ValueError("deliver_split blocked: decision rulers not locked")

    slices = slices_from_locked_tree(locked_tree)
    pkg_path = root / "decision-package.json"
    if pkg_path.is_file():
        package = load_decision_package(pkg_path)
        package["slices"] = slices
        package["status"] = "split_delivered"
    else:
        package = build_decision_package(
            main=conventional_main_paths(),
            slices=slices,
            status="split_delivered",
        )
    save_decision_package(root, package)

    shell["split_delivered"] = True
    save_shell(root, shell)
    return {
        "ok": True,
        "split_delivered": True,
        "slices": slices,
        "package": package,
        "tree": locked_tree,
    }


def ensure_dx_on_focus(approach_root: Path, node_id: str) -> Path:
    """Lazy-create ``Dx/`` on first Working focus (S3=B)."""
    root = Path(approach_root).resolve()
    sid = str(node_id).strip()
    if not _DX_ID_RE.match(sid):
        raise ValueError(f"ensure_dx_on_focus expects D<number>, got {node_id!r}")
    ensure_approach_layout(root, dx_ids=[sid])
    return dx_session_dir(root, sid)


# Re-export builders for tests / callers
__all__ = [
    "build_decision_rulers",
    "build_tree",
    "complete_intake",
    "conventional_main_paths",
    "conventional_slice_paths",
    "deliver_split",
    "empty_intake",
    "ensure_dx_on_focus",
    "lock_tree_and_rulers",
    "slices_from_locked_tree",
    "write_early_package",
    "write_intake",
]
