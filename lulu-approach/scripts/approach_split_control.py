#!/usr/bin/env python3
"""Approach Split structural-cut helpers (archive-1.0 P2.split).

Locked S1–S4:
  - decision-oriented minimal intake
  - lock dependency-tree + decision rulers
  - Split Delivered writes ``decision-package.slices`` with conventional
    relative paths (files may not exist yet)
  - ``Dx/`` created only on first Working focus

CLI (stdout JSON ``{"ok": true, ...}``; errors on stderr, exit 1)::

    python3 approach_split_control.py --approach-root <path> <subcommand> ...

Subcommands: write-early-package, write-intake, complete-intake,
lock-tree-rulers, complete-split (alias: deliver-split).
"""

from __future__ import annotations

import argparse
import json
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
from approach_mainline_reopen_schema import (  # noqa: E402
    load_mainline_reopen,
    save_mainline_reopen,
)
from approach_shell_schema import load_shell, save_shell  # noqa: E402
from approach_split_candidate_schema import (  # noqa: E402
    materialize_candidate,
    save_candidate,
    structure_signature,
)
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
from approach_dependency_tree_schema import (  # noqa: E402
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


def write_reopen_candidate(
    approach_root: Path,
    *,
    transaction_id: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Persist a Split-review candidate without replacing current Working artifacts."""
    root = Path(approach_root).resolve()
    transaction = load_mainline_reopen(root)
    if transaction["transaction_id"] != str(transaction_id).strip():
        raise ValueError("write-reopen-candidate transaction-id does not match")
    if transaction["state"] != "split_review":
        raise ValueError(
            "write-reopen-candidate requires split_review transaction, "
            f"got {transaction['state']!r}"
        )
    old_tree = load_dependency_tree(root)
    old_ids = {str(node["id"]) for node in old_tree["nodes"]}
    tree, _ = materialize_candidate(candidate)
    for candidate_id, mapping in candidate["mapping"].items():
        node_id = mapping["node_id"]
        if mapping["kind"] == "existing" and node_id not in old_ids:
            raise ValueError(
                f"candidate mapping {candidate_id!r} references missing old node {node_id!r}"
            )
        if mapping["kind"] == "new" and node_id in old_ids:
            raise ValueError(
                f"candidate mapping {candidate_id!r} marks existing node {node_id!r} as new"
            )
    path = save_candidate(root, transaction["transaction_id"], candidate)
    old_signature = structure_signature(old_tree)
    candidate_signature = structure_signature(tree)
    transaction["old_graph_snapshot"] = (root / "dependency-tree.json").as_posix()
    transaction["candidate_graph_snapshot"] = path.as_posix()
    transaction["candidate_id_mapping"] = dict(candidate["mapping"])
    transaction["structure_signature"] = {
        "old": old_signature,
        "candidate": candidate_signature,
    }
    save_mainline_reopen(root, transaction)
    return {
        "ok": True,
        "command": "write-reopen-candidate",
        "transaction_id": transaction["transaction_id"],
        "candidate_path": path.as_posix(),
        "structure_signature": dict(transaction["structure_signature"]),
        "structure_match": old_signature == candidate_signature,
    }


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


def complete_split(
    approach_root: Path,
    *,
    tree: dict[str, Any] | None = None,
    rulers: dict[str, Any] | None = None,
    confirm: bool,
) -> dict[str, Any]:
    """Split complete: lock tree+rulers, write ordered slices, mark shell.

    Does **not** create ``Dx/`` directories (S3=B).
    """
    if not confirm:
        raise ValueError("complete_split blocked: human --confirm required")
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    if shell["macro_state"] != "Split":
        raise ValueError(
            f"complete_split requires macro_state=Split, got {shell['macro_state']!r}"
        )

    if tree is not None and rulers is not None:
        locked_tree, _ = lock_tree_and_rulers(
            root, tree=tree, rulers=rulers, confirm=True
        )
    else:
        locked_tree = load_dependency_tree(root)
        if locked_tree.get("status") != "locked":
            raise ValueError("complete_split blocked: dependency tree not locked")
        locked_rulers = load_decision_rulers(root)
        if locked_rulers.get("status") != "locked":
            raise ValueError("complete_split blocked: decision rulers not locked")

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
        "split_completed": True,
        "split_delivered": True,  # legacy key
        "slices": slices,
        "package": package,
        "tree": locked_tree,
    }


def deliver_split(
    approach_root: Path,
    *,
    tree: dict[str, Any] | None = None,
    rulers: dict[str, Any] | None = None,
    confirm: bool,
) -> dict[str, Any]:
    """Deprecated alias for ``complete_split``."""
    return complete_split(
        approach_root, tree=tree, rulers=rulers, confirm=confirm
    )


def ensure_dx_on_focus(approach_root: Path, node_id: str) -> Path:
    """Lazy-create ``Dx/`` on first Working focus (S3=B)."""
    root = Path(approach_root).resolve()
    sid = str(node_id).strip()
    if not _DX_ID_RE.match(sid):
        raise ValueError(f"ensure_dx_on_focus expects D<number>, got {node_id!r}")
    ensure_approach_layout(root, dx_ids=[sid])
    return dx_session_dir(root, sid)


def _load_json_arg(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _emit_ok(payload: dict[str, Any]) -> int:
    out = dict(payload)
    out.setdefault("ok", True)
    print(json.dumps(out, ensure_ascii=False))
    return 0


def _emit_err(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="approach_split_control.py",
        description="Approach Split structural-cut control.",
    )
    p.add_argument("--approach-root", required=True, type=Path)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "write-early-package",
        help="Write decision-package with empty slices",
    )

    p_wi = sub.add_parser("write-intake", help="Write draft split intake")
    p_wi.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        default=None,
        help="Optional intake JSON object path",
    )

    p_ci = sub.add_parser("complete-intake", help="Mark intake complete")
    p_ci.add_argument("--confirm", action="store_true")

    p_lock = sub.add_parser(
        "lock-tree-rulers",
        help="Lock dependency-tree + decision rulers",
    )
    p_lock.add_argument("--tree", required=True, type=Path)
    p_lock.add_argument("--rulers", required=True, type=Path)
    p_lock.add_argument("--confirm", action="store_true")

    for cmd_name, help_text in (
        ("complete-split", "Mark Split complete + write slices"),
        ("deliver-split", "Deprecated alias for complete-split"),
    ):
        p_ds = sub.add_parser(cmd_name, help=help_text)
        p_ds.add_argument("--tree", type=Path, default=None)
        p_ds.add_argument("--rulers", type=Path, default=None)
        p_ds.add_argument("--confirm", action="store_true")

    p_wrc = sub.add_parser(
        "write-reopen-candidate",
        help="Store a temporary C-node candidate during Split review",
    )
    p_wrc.add_argument("--transaction-id", required=True)
    p_wrc.add_argument("--candidate", required=True, type=Path)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    root = Path(args.approach_root).resolve()
    try:
        if args.command == "write-early-package":
            return _emit_ok({"package": write_early_package(root)})
        if args.command == "write-intake":
            data = _load_json_arg(args.json_path)
            return _emit_ok({"intake": write_intake(root, data)})
        if args.command == "complete-intake":
            return _emit_ok(
                {"intake": complete_intake(root, confirm=bool(args.confirm))}
            )
        if args.command == "lock-tree-rulers":
            tree = _load_json_arg(args.tree)
            rulers = _load_json_arg(args.rulers)
            if tree is None or rulers is None:
                raise ValueError("lock-tree-rulers requires --tree and --rulers JSON")
            locked_tree, locked_rulers = lock_tree_and_rulers(
                root, tree=tree, rulers=rulers, confirm=bool(args.confirm)
            )
            return _emit_ok({"tree": locked_tree, "rulers": locked_rulers})
        if args.command in {"complete-split", "deliver-split"}:
            tree = _load_json_arg(args.tree)
            rulers = _load_json_arg(args.rulers)
            return _emit_ok(
                complete_split(
                    root,
                    tree=tree,
                    rulers=rulers,
                    confirm=bool(args.confirm),
                )
            )
        if args.command == "write-reopen-candidate":
            candidate = _load_json_arg(args.candidate)
            if candidate is None:
                raise ValueError("write-reopen-candidate requires --candidate JSON")
            return _emit_ok(
                write_reopen_candidate(
                    root,
                    transaction_id=args.transaction_id,
                    candidate=candidate,
                )
            )
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
        return _emit_err(str(exc))
    return _emit_err(f"unknown command: {args.command}")


# Re-export builders for tests / callers
__all__ = [
    "build_decision_rulers",
    "build_tree",
    "complete_intake",
    "conventional_main_paths",
    "conventional_slice_paths",
    "complete_split",
    "deliver_split",
    "empty_intake",
    "ensure_dx_on_focus",
    "lock_tree_and_rulers",
    "main",
    "slices_from_locked_tree",
    "write_early_package",
    "write_intake",
    "write_reopen_candidate",
]


if __name__ == "__main__":
    raise SystemExit(main())
