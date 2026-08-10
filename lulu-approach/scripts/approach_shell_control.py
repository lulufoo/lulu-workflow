#!/usr/bin/env python3
"""Approach outer-shell control (archive-1.0 P2.shell).

Macro transitions::

    Main → Split → Working → PackageReady
    Main → PackageReady          (no-split shortcut)

Working: single focus; reject mid-switch until current focus is Completed.
PackageReady: human ``--confirm`` required before stage ``deliver`` (Path A:
selection may authorize confirm without a second ask).

Node-complete stub: prefer ``by_id[].delivered``; else ``session-state.md``
``current_state: Completed`` under ``main/`` or ``Dx/`` when present.

CLI (stdout JSON ``{"ok": true, ...}``; errors on stderr, exit 1)::

    python3 approach_shell_control.py --approach-root <path> <subcommand> ...

    Subcommands: init-shell, enter-split, enter-working, enter-node,
enter-package-ready, deliver (alias confirm-seal), freeze-cascade, reopen-node,
complete-reopen, recover-binding, bind-check-frozen, clear-frozen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_SCHEMA = _SCRIPTS / "schema"
_WORKFLOW_SCRIPTS = _SCRIPTS.parents[1] / "scripts"
_DECISION_SCRIPTS = _SCRIPTS.parents[1] / "decision" / "scripts"
for _p in (_SCRIPTS, _SCHEMA, _WORKFLOW_SCRIPTS, _DECISION_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from approach_dependency_tree_schema import load_dependency_tree, save_dependency_tree  # noqa: E402
from approach_node_binding_schema import (  # noqa: E402
    build_node_binding,
    load_node_binding,
    new_binding_id,
    node_binding_path,
    save_node_binding,
    try_load_node_binding,
)
from approach_layout import (  # noqa: E402
    decision_package_path,
    dx_session_dir,
    ensure_approach_layout,
    main_session_dir,
    source_package_path,
)
from approach_mainline_reopen_schema import (  # noqa: E402
    build_mainline_reopen,
    load_mainline_reopen,
    new_transaction_id,
    save_mainline_reopen,
)
from approach_shell_schema import (  # noqa: E402
    empty_cell,
    initial_shell,
    load_shell,
    save_shell,
    shell_path,
)
from approach_split_control import (  # noqa: E402
    conventional_main_paths,
    slices_from_locked_tree,
    write_early_package,
)
from approach_split_candidate_schema import (  # noqa: E402
    load_candidate,
    materialize_candidate,
    structure_signature,
)
from approach_working_archive import archive_working_generation  # noqa: E402
from cycle_delivered_refs import delivered_refs_file_path, record_delivered_ref  # noqa: E402
from decision_package_schema import (  # noqa: E402
    build_decision_package,
    load_decision_package,
    save_decision_package,
)
from decision_rulers_schema import save_decision_rulers  # noqa: E402
from dec_lifecycle import bind_session, freeze_session, unfreeze_session_public  # noqa: E402
import resolve_context  # noqa: E402

_DX_ID_RE = re.compile(r"^D\d+$")
_SESSION_STATE = "session-state.md"


def ensure_dx_on_focus(approach_root: Path, node_id: str) -> Path:
    """Lazy-create ``Dx/`` on first Working focus (P2.split S3=B)."""
    root = Path(approach_root).resolve()
    sid = str(node_id).strip()
    if not _DX_ID_RE.match(sid):
        raise ValueError(f"ensure_dx_on_focus expects D<number>, got {node_id!r}")
    ensure_approach_layout(root, dx_ids=[sid])
    return dx_session_dir(root, sid)


def init_shell(approach_root: Path) -> dict[str, Any]:
    """Create approach layout + initial Main shell pointer."""
    root = ensure_approach_layout(approach_root)
    shell = initial_shell()
    save_shell(root, shell)
    return shell


def _parse_session_state_current(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    for line in text[3:end].splitlines():
        line = line.strip()
        if line.startswith("current_state:"):
            return line.split(":", 1)[1].strip()
    return None


def _session_dir_for_node(approach_root: Path, node_id: str) -> Path:
    root = Path(approach_root).resolve()
    if node_id == "main":
        return main_session_dir(root)
    if not _DX_ID_RE.match(node_id):
        raise ValueError(f"node_id must be main|D<number>, got {node_id!r}")
    return dx_session_dir(root, node_id)


def is_node_delivered(approach_root: Path, node_id: str, shell: dict[str, Any] | None = None) -> bool:
    """True when node session is Completed (shell completed/delivered ∧ ¬frozen)."""
    nid = str(node_id).strip()
    data = shell if shell is not None else load_shell(approach_root)
    if nid != "main":
        cell = (data.get("by_id") or {}).get(nid)
        if isinstance(cell, dict) and cell.get("frozen") is True:
            return False
        if isinstance(cell, dict) and (
            cell.get("completed") is True or cell.get("delivered") is True
        ):
            return True
    session_dir = _session_dir_for_node(approach_root, nid)
    state = _parse_session_state_current(session_dir / _SESSION_STATE)
    if state == "Frozen":
        return False
    return state in {"Completed", "Delivered"}


def mark_node_delivered(approach_root: Path, node_id: str) -> dict[str, Any]:
    """Mark a Dx cell delivered in the shell pointer (test / stub helper)."""
    nid = str(node_id).strip()
    if not _DX_ID_RE.match(nid):
        raise ValueError(f"mark_node_delivered expects D<number>, got {nid!r}")
    shell = load_shell(approach_root)
    by_id = dict(shell.get("by_id") or {})
    if nid not in by_id:
        raise ValueError(f"unknown node {nid!r}")
    cell = dict(by_id[nid])
    cell["delivered"] = True
    cell["phase"] = "pending"
    by_id[nid] = cell
    shell["by_id"] = by_id
    save_shell(approach_root, shell)
    return shell


def mark_split_delivered(approach_root: Path) -> dict[str, Any]:
    """Mark Split Delivered flag only (tests / stub). Prefer ``deliver_split``."""
    shell = load_shell(approach_root)
    if shell["macro_state"] != "Split":
        raise ValueError(
            f"mark_split_delivered requires macro_state=Split, got {shell['macro_state']!r}"
        )
    shell["split_delivered"] = True
    save_shell(approach_root, shell)
    return shell


def enter_split(approach_root: Path) -> dict[str, Any]:
    """Main → Split. Requires parent (main) Delivered. Never auto from start."""
    shell = load_shell(approach_root)
    if shell["macro_state"] != "Main":
        raise ValueError(
            f"enter_split requires macro_state=Main, got {shell['macro_state']!r}"
        )
    if not is_node_delivered(approach_root, "main", shell):
        raise ValueError("enter_split blocked: main is not Completed")
    shell["macro_state"] = "Split"
    shell["focus"] = "main"
    shell["split_delivered"] = False
    save_shell(approach_root, shell)
    return shell


def enter_working(
    approach_root: Path,
    node_ids: list[str],
    *,
    focus: str | None = None,
) -> dict[str, Any]:
    """Split → Working. Requires Split Delivered stub; seeds by_id + single focus."""
    shell = load_shell(approach_root)
    if shell["macro_state"] != "Split":
        raise ValueError(
            f"enter_working requires macro_state=Split, got {shell['macro_state']!r}"
        )
    if not shell.get("split_delivered"):
        raise ValueError("enter_working blocked: Split is not completed")
    ids = [str(n).strip() for n in node_ids]
    if not ids:
        raise ValueError("enter_working requires non-empty node_ids")
    for nid in ids:
        if not _DX_ID_RE.match(nid):
            raise ValueError(f"node_id must match D<number>, got {nid!r}")
    if len(set(ids)) != len(ids):
        raise ValueError("node_ids must be unique")
    focus_id = str(focus).strip() if focus else ids[0]
    if focus_id not in ids:
        raise ValueError(f"focus {focus_id!r} not in node_ids")
    # S3=B: create only the focused Dx/; others wait for set_focus
    ensure_approach_layout(approach_root)
    ensure_dx_on_focus(approach_root, focus_id)
    by_id = {nid: empty_cell(phase="pending") for nid in ids}
    by_id[focus_id] = empty_cell(phase="in_progress")
    shell["macro_state"] = "Working"
    shell["focus"] = focus_id
    shell["by_id"] = by_id
    save_shell(approach_root, shell)
    dx = ensure_dx_on_focus(approach_root, focus_id)
    return {
        **shell,
        "next_steps": {
            "session_dir": dx.as_posix(),
            "require": [
                "APPROACH_SHELL enter-node for focused Dx",
            ],
        },
    }


def set_focus(approach_root: Path, node_id: str) -> dict[str, Any]:
    """Retired public focus switch; callers must use the binding protocol."""
    del approach_root, node_id
    raise ValueError("set_focus is retired; use enter-node")


def commit_focus(approach_root: Path, node_id: str) -> dict[str, Any]:
    """Internal shell-only focus commit after a decision binding succeeds."""
    shell = load_shell(approach_root)
    if shell["macro_state"] != "Working":
        raise ValueError(
            f"set_focus requires macro_state=Working, got {shell['macro_state']!r}"
        )
    target = str(node_id).strip()
    by_id = dict(shell.get("by_id") or {})
    if target not in by_id:
        raise ValueError(f"unknown focus target {target!r}")
    current = shell.get("focus")
    if current == target:
        dx = ensure_dx_on_focus(approach_root, target)
        return {**shell, "next_steps": _bind_next_steps(dx)}
    if current is not None and not is_node_delivered(approach_root, str(current), shell):
        raise ValueError(
            f"focus switch blocked: current focus {current!r} is not Completed"
        )
    # E1: target may be Frozen (enter cascade-successor for bind → realign).
    if current is not None and current in by_id:
        prev = dict(by_id[current])
        if prev.get("phase") == "in_progress":
            prev["phase"] = "pending"
        by_id[current] = prev
    cell = dict(by_id[target])
    cell["phase"] = "in_progress"
    by_id[target] = cell
    shell["focus"] = target
    shell["by_id"] = by_id
    save_shell(approach_root, shell)
    dx = ensure_dx_on_focus(approach_root, target)
    return {**shell, "next_steps": _bind_next_steps(dx)}


def _frozen_ids(shell: dict[str, Any]) -> list[str]:
    return sorted(
        nid
        for nid, cell in (shell.get("by_id") or {}).items()
        if isinstance(cell, dict) and cell.get("frozen") is True
    )


def _successor_closure(tree: dict[str, Any], node_id: str) -> list[str]:
    """Target plus transitive dependents.

    Tree edge ``from=Dx,to=Dy`` means Dx depends on Dy (Dy precedes Dx).
    """
    nid = str(node_id).strip()
    nodes = {
        str(n.get("id", "")).strip()
        for n in (tree.get("nodes") or [])
        if isinstance(n, dict)
    }
    if nid not in nodes:
        raise ValueError(f"freeze-cascade unknown node {nid!r}")
    dependents: dict[str, list[str]] = defaultdict(list)
    for edge in tree.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        frm = str(edge.get("from", "")).strip()
        to = str(edge.get("to", "")).strip()
        if frm and to:
            dependents[to].append(frm)
    out: list[str] = []
    seen: set[str] = set()
    q: deque[str] = deque([nid])
    while q:
        cur = q.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        out.append(cur)
        for child in dependents.get(cur, []):
            if child not in seen:
                q.append(child)
    return out


def _try_freeze_session(session_dir: Path) -> str:
    """Return session_frozen | already_frozen | skipped."""
    state = _parse_session_state_current(session_dir / _SESSION_STATE)
    if state is None:
        return "skipped"
    if state == "Frozen":
        return "already_frozen"
    if state in {"Delivered", "InProgress"}:
        freeze_session(session_dir)
        return "session_frozen"
    return "skipped"


def _bind_next_steps(session_dir: Path) -> dict[str, Any]:
    return {
        "session_dir": session_dir.as_posix(),
        "require": [
            "GATE_CONTROL resolve-context",
            "load context_docs",
            "declare session switched",
            "APPROACH_SHELL bind-check-frozen",
            "if realign_required: semantic Realign then APPROACH_SHELL clear-frozen",
        ],
    }


def freeze_cascade(approach_root: Path, node_id: str) -> dict[str, Any]:
    """Freeze node_id and DAG successors (shell + session when present)."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    if shell.get("macro_state") != "Working":
        raise ValueError(
            f"freeze-cascade requires macro_state=Working, got {shell.get('macro_state')!r}"
        )
    try:
        tree = load_dependency_tree(root)
    except FileNotFoundError as exc:
        raise ValueError(f"freeze-cascade blocked: {exc}") from exc
    if str(tree.get("status", "")).strip() != "locked":
        raise ValueError(
            f"freeze-cascade blocked: dependency tree status must be locked, "
            f"got {tree.get('status')!r}"
        )
    target = str(node_id).strip()
    if not _DX_ID_RE.match(target):
        raise ValueError(f"freeze-cascade expects D<number>, got {target!r}")
    closure = _successor_closure(tree, target)
    by_id = dict(shell.get("by_id") or {})
    session_frozen: list[str] = []
    shell_only: list[str] = []
    for nid in closure:
        cell = dict(by_id.get(nid) or empty_cell())
        cell["frozen"] = True
        by_id[nid] = cell
        dx = dx_session_dir(root, nid)
        if not dx.is_dir():
            shell_only.append(nid)
            continue
        result = _try_freeze_session(dx)
        if result in {"session_frozen", "already_frozen"}:
            session_frozen.append(nid)
        else:
            shell_only.append(nid)
    shell["by_id"] = by_id
    save_shell(root, shell)
    return {
        "ok": True,
        "command": "freeze-cascade",
        "node_id": target,
        "frozen_ids": closure,
        "session_frozen": session_frozen,
        "shell_only": shell_only,
        "shell": shell,
    }


def force_commit_focus(approach_root: Path, node_id: str) -> dict[str, Any]:
    """Internally commit focus without requiring current focus Delivered."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    if shell["macro_state"] != "Working":
        raise ValueError(
            f"force_commit_focus requires macro_state=Working, got {shell['macro_state']!r}"
        )
    target = str(node_id).strip()
    by_id = dict(shell.get("by_id") or {})
    if target not in by_id:
        raise ValueError(f"unknown focus target {target!r}")
    current = shell.get("focus")
    if current is not None and current in by_id and current != target:
        prev = dict(by_id[current])
        if prev.get("phase") == "in_progress":
            prev["phase"] = "pending"
        by_id[current] = prev
    cell = dict(by_id[target])
    cell["phase"] = "in_progress"
    by_id[target] = cell
    shell["focus"] = target
    shell["by_id"] = by_id
    save_shell(root, shell)
    dx = ensure_dx_on_focus(root, target)
    return {**shell, "next_steps": _bind_next_steps(dx)}


def _locked_working_tree(approach_root: Path, node_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the Working shell and its locked tree after target validation."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    if shell.get("macro_state") != "Working":
        raise ValueError(
            f"node binding requires macro_state=Working, got {shell.get('macro_state')!r}"
        )
    target = str(node_id).strip()
    if not _DX_ID_RE.match(target) or target not in (shell.get("by_id") or {}):
        raise ValueError(f"unknown node binding target {target!r}")
    try:
        tree = load_dependency_tree(root)
    except FileNotFoundError as exc:
        raise ValueError(f"node binding blocked: {exc}") from exc
    if str(tree.get("status", "")).strip() != "locked":
        raise ValueError(
            "node binding blocked: dependency tree status must be locked, "
            f"got {tree.get('status')!r}"
        )
    _successor_closure(tree, target)
    return shell, tree


def _active_session_name(approach_root: Path) -> str | None:
    """Read the holder's Active pointer without importing its low-level schema."""
    path = Path(approach_root).resolve() / "active-session.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("active-session must be a JSON object")
    session_dir = str(data.get("session_dir", "")).strip()
    if session_dir in {"main"} or _DX_ID_RE.match(session_dir):
        return session_dir
    raise ValueError(f"active-session has invalid session_dir {session_dir!r}")


def _require_no_unrecovered_binding(approach_root: Path) -> None:
    existing = try_load_node_binding(approach_root)
    if existing is None or existing["state"] == "bound":
        return
    raise ValueError(
        "node binding blocked: unresolved transaction "
        f"{existing['binding_id']!r} is {existing['state']!r}; use recover-binding"
    )


def _start_binding(
    approach_root: Path,
    node_id: str,
    *,
    operation: str,
) -> dict[str, Any]:
    _require_no_unrecovered_binding(approach_root)
    shell = load_shell(approach_root)
    target = str(node_id).strip()
    binding = build_node_binding(
        binding_id=new_binding_id(),
        state="preparing",
        previous={
            "focus": shell.get("focus"),
            "active_session": _active_session_name(approach_root),
        },
        target={"node_id": target, "session_dir": target},
        operation=operation,
    )
    save_node_binding(approach_root, binding)
    return binding


def _save_failed_binding(approach_root: Path, binding: dict[str, Any]) -> None:
    binding["state"] = "failed"
    save_node_binding(approach_root, binding)


def _snapshot_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind_node(
    approach_root: Path,
    node_id: str,
    *,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
    binding: dict[str, Any],
    force: bool,
) -> dict[str, Any]:
    """Complete the context → decision → shell half of one binding transaction."""
    root = Path(approach_root).resolve()
    target = str(node_id).strip()
    session_dir = ensure_dx_on_focus(root, target)
    try:
        snapshot_path = resolve_context.write_resolved_context(
            Path(project_root).resolve(),
            str(cycle_id).strip(),
            Path(constraints_path).resolve(),
            session_dir=session_dir,
            binding_id=binding["binding_id"],
        )
    except (FileNotFoundError, ValueError, OSError):
        _save_failed_binding(root, binding)
        raise
    binding["context_snapshot"] = {
        "path": snapshot_path.resolve().as_posix(),
        "sha256": _snapshot_sha256(snapshot_path),
    }
    save_node_binding(root, binding)

    mode = (
        "existing"
        if (session_dir / "gate-state.json").is_file()
        or (session_dir / "domain-constraints.json").is_file()
        else "initialize"
    )
    try:
        decision = bind_session(
            Path(project_root).resolve(),
            str(cycle_id).strip(),
            session_dir=session_dir,
            resolved_context_path=snapshot_path,
            mode=mode,
            constraints_path=Path(constraints_path).resolve(),
        )
    except (FileNotFoundError, ValueError, OSError):
        _save_failed_binding(root, binding)
        raise

    binding["state"] = "decision_bound"
    save_node_binding(root, binding)
    shell = force_commit_focus(root, target) if force else commit_focus(root, target)
    return {
        "decision": decision,
        "shell": shell,
        "context_snapshot": dict(binding["context_snapshot"]),
    }


def _bind_main(
    approach_root: Path,
    *,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
    binding: dict[str, Any],
) -> dict[str, Any]:
    """Bind Main context and Active Session without a Working focus commit."""
    root = Path(approach_root).resolve()
    session_dir = main_session_dir(root)
    try:
        snapshot_path = resolve_context.write_resolved_context(
            Path(project_root).resolve(),
            str(cycle_id).strip(),
            Path(constraints_path).resolve(),
            session_dir=session_dir,
            binding_id=binding["binding_id"],
        )
        binding["context_snapshot"] = {
            "path": snapshot_path.resolve().as_posix(),
            "sha256": _snapshot_sha256(snapshot_path),
        }
        save_node_binding(root, binding)
        mode = (
            "existing"
            if (session_dir / "gate-state.json").is_file()
            or (session_dir / "domain-constraints.json").is_file()
            else "initialize"
        )
        decision = bind_session(
            Path(project_root).resolve(),
            str(cycle_id).strip(),
            session_dir=session_dir,
            resolved_context_path=snapshot_path,
            mode=mode,
            constraints_path=Path(constraints_path).resolve(),
        )
    except (FileNotFoundError, ValueError, OSError):
        _save_failed_binding(root, binding)
        raise
    binding["state"] = "decision_bound"
    save_node_binding(root, binding)
    return {
        "decision": decision,
        "context_snapshot": dict(binding["context_snapshot"]),
    }


def enter_reopen_split(approach_root: Path) -> dict[str, Any]:
    """Enter the controlled Split review after Main or Split reopen."""
    root = Path(approach_root).resolve()
    transaction = load_mainline_reopen(root)
    if transaction["state"] not in {"main_repaired", "split_pending"}:
        raise ValueError(
            "enter-node split requires main_repaired|split_pending transaction, "
            f"got {transaction['state']!r}"
        )
    if _active_session_name(root) != "main":
        raise ValueError("enter-node split requires Main to remain Active")
    shell = load_shell(root)
    allowed_macros = (
        {"Main"} if transaction["state"] == "main_repaired" else {"SplitReopen"}
    )
    if shell["macro_state"] not in allowed_macros:
        raise ValueError(
            "enter-node split has incompatible macro_state "
            f"{shell['macro_state']!r}"
        )
    shell["macro_state"] = "SplitReopen"
    shell["focus"] = "main"
    save_shell(root, shell)
    transaction["state"] = "split_review"
    save_mainline_reopen(root, transaction)
    return {
        "ok": True,
        "command": "enter-node",
        "node_id": "split",
        "transaction_id": transaction["transaction_id"],
        "shell": shell,
        "next_steps": {
            "require": [
                "generate temporary C<n> candidate topology and C-to-D mapping",
                "write-reopen-candidate",
                "show structural difference and archive impact",
                "complete-split-reopen --confirm",
            ]
        },
    }


def enter_node(
    approach_root: Path,
    node_id: str,
    *,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
    force: bool = False,
) -> dict[str, Any]:
    """Public complete entry: bind context, Active Session, then shell focus."""
    root = Path(approach_root).resolve()
    target = str(node_id).strip()
    if target == "split":
        return enter_reopen_split(root)
    shell = load_shell(root)
    if target == "main":
        if shell["macro_state"] != "Main":
            raise ValueError(
                f"enter-node main requires macro_state=Main, got {shell['macro_state']!r}"
            )
        binding = _start_binding(root, "main", operation="enter")
        result = _bind_main(
            root,
            project_root=project_root,
            cycle_id=cycle_id,
            constraints_path=constraints_path,
            binding=binding,
        )
        shell["focus"] = "main"
        save_shell(root, shell)
        binding["state"] = "bound"
        save_node_binding(root, binding)
        return {
            "ok": True,
            "command": "enter-node",
            "node_id": "main",
            "binding_id": binding["binding_id"],
            "session_dir": result["decision"]["session_dir"],
            "context_docs": result["decision"]["context_docs"],
            "context_snapshot": result["context_snapshot"],
            "initialized": result["decision"]["initialized"],
            "shell": shell,
        }
    if shell["macro_state"] == "SplitReopen":
        transaction = load_mainline_reopen(root)
        if transaction["state"] not in {"working_retained", "working_rebuilt"}:
            raise ValueError("SplitReopen only permits Dx entry after Split confirmation")
        if not _DX_ID_RE.match(target) or target not in shell["by_id"]:
            raise ValueError(f"unknown node binding target {target!r}")
        cell = dict(shell["by_id"][target])
        cell["phase"] = "in_progress"
        shell["by_id"][target] = cell
        shell["macro_state"] = "Working"
        shell["focus"] = target
        save_shell(root, shell)
        binding = _start_binding(root, target, operation="enter")
        result = bind_node(
            root,
            target,
            project_root=project_root,
            cycle_id=cycle_id,
            constraints_path=constraints_path,
            binding=binding,
            force=True,
        )
        binding["state"] = "bound"
        save_node_binding(root, binding)
        return {
            "ok": True,
            "command": "enter-node",
            "node_id": target,
            "binding_id": binding["binding_id"],
            "session_dir": result["decision"]["session_dir"],
            "context_docs": result["decision"]["context_docs"],
            "context_snapshot": result["context_snapshot"],
            "initialized": result["decision"]["initialized"],
            "shell": result["shell"],
        }
    _locked_working_tree(root, node_id)
    binding = _start_binding(root, node_id, operation="enter")
    result = bind_node(
        root,
        node_id,
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=constraints_path,
        binding=binding,
        force=force,
    )
    binding["state"] = "bound"
    save_node_binding(root, binding)
    return {
        "ok": True,
        "command": "enter-node",
        "node_id": str(node_id).strip(),
        "binding_id": binding["binding_id"],
        "session_dir": result["decision"]["session_dir"],
        "context_docs": result["decision"]["context_docs"],
        "context_snapshot": result["context_snapshot"],
        "initialized": result["decision"]["initialized"],
        "shell": result["shell"],
        "next_steps": {
            "require": [
                "GATE_CONTROL resolve-context",
                "load context_docs",
                "declare session switched",
                "APPROACH_SHELL bind-check-frozen",
            ]
        },
    }


def _freeze_reopen_closure(
    approach_root: Path,
    *,
    target: str,
    closure: list[str],
    binding: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Freeze all shell cells, but decision sessions for successors only."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    by_id = dict(shell.get("by_id") or {})
    session_frozen: list[str] = []
    shell_only: list[str] = []
    try:
        for node_id in closure:
            cell = dict(by_id[node_id])
            cell["frozen"] = True
            by_id[node_id] = cell
            shell["by_id"] = by_id
            save_shell(root, shell)
            if node_id not in binding["frozen_nodes"]:
                binding["frozen_nodes"].append(node_id)
                save_node_binding(root, binding)
            if node_id == target:
                continue
            session_dir = dx_session_dir(root, node_id)
            if not session_dir.is_dir():
                shell_only.append(node_id)
                continue
            state = _try_freeze_session(session_dir)
            if state in {"session_frozen", "already_frozen"}:
                session_frozen.append(node_id)
            else:
                shell_only.append(node_id)
    except (FileNotFoundError, ValueError, OSError):
        _save_failed_binding(root, binding)
        raise
    return shell, session_frozen, shell_only


def _permit_path(approach_root: Path, binding_id: str) -> Path:
    return Path(approach_root).resolve() / "bindings" / binding_id / "permit.json"


def _issue_reopen_permit(approach_root: Path, binding: dict[str, Any], cycle_id: str) -> Path:
    path = _permit_path(approach_root, binding["binding_id"])
    payload = {
        "version": "1",
        "kind": "lulu-approach-reopen",
        "binding_id": binding["binding_id"],
        "cycle_id": str(cycle_id).strip(),
        "stage": "lulu-approach",
        "node_id": binding["target"]["node_id"],
        "session_dir": binding["target"]["session_dir"],
        "state": "issued",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    binding["permit_path"] = path.resolve().as_posix()
    binding["permit_state"] = "issued"
    binding["state"] = "reopen_pending"
    save_node_binding(approach_root, binding)
    return path


def _reopen_dx(
    approach_root: Path,
    node_id: str,
    *,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> dict[str, Any]:
    """Prepare a permit-backed reopen without freezing the target session."""
    root = Path(approach_root).resolve()
    _, tree = _locked_working_tree(root, node_id)
    target = str(node_id).strip()
    closure = _successor_closure(tree, target)
    binding = _start_binding(root, target, operation="reopen")
    _, session_frozen, shell_only = _freeze_reopen_closure(
        root,
        target=target,
        closure=closure,
        binding=binding,
    )
    result = bind_node(
        root,
        target,
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=constraints_path,
        binding=binding,
        force=True,
    )
    try:
        permit_path = _issue_reopen_permit(root, binding, cycle_id)
    except OSError:
        _save_failed_binding(root, binding)
        raise
    return {
        "ok": True,
        "command": "reopen-node",
        "node_id": target,
        "binding_id": binding["binding_id"],
        "permit_path": permit_path.resolve().as_posix(),
        "context_docs": result["decision"]["context_docs"],
        "context_snapshot": result["context_snapshot"],
        "frozen_ids": list(binding["frozen_nodes"]),
        "session_frozen": session_frozen,
        "shell_only": shell_only,
        "shell": result["shell"],
        "next_steps": {
            "require": [
                f"DEC_REOPEN --permit {permit_path.resolve().as_posix()}",
                "GATE_CONTROL resolve-context",
                "load context_docs",
                "declare session switched",
            ]
        },
    }


def _start_mainline_reopen(
    approach_root: Path,
    *,
    target: str,
) -> dict[str, Any]:
    """Persist the Main/Split transaction before mutating its closure."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    if shell["macro_state"] not in {"Main", "Split", "Working"}:
        raise ValueError(
            f"reopen-node {target} requires Main|Split|Working, "
            f"got {shell['macro_state']!r}"
        )
    transaction = build_mainline_reopen(
        transaction_id=new_transaction_id(),
        target={"kind": target, "node_id": target},
        state="preparing",
        previous={
            "macro_state": shell["macro_state"],
            "focus": shell.get("focus"),
            "active_session": _active_session_name(root),
        },
        frozen={"split": target == "main", "nodes": []},
    )
    save_mainline_reopen(root, transaction)
    return transaction


def reopen_main(
    approach_root: Path,
    *,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> dict[str, Any]:
    """Freeze Working, bind Main, and issue the Main decision reopen permit."""
    root = Path(approach_root).resolve()
    transaction = _start_mainline_reopen(root, target="main")
    shell = load_shell(root)
    binding = _start_binding(root, "main", operation="reopen")
    _, session_frozen, shell_only = _freeze_reopen_closure(
        root,
        target="main",
        closure=list((shell.get("by_id") or {}).keys()),
        binding=binding,
    )
    transaction["frozen"] = {
        "split": True,
        "nodes": list(binding["frozen_nodes"]),
    }
    transaction["state"] = "downstream_frozen"
    save_mainline_reopen(root, transaction)
    result = _bind_main(
        root,
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=constraints_path,
        binding=binding,
    )
    shell = load_shell(root)
    shell["macro_state"] = "MainReopen"
    shell["focus"] = "main"
    save_shell(root, shell)
    try:
        permit_path = _issue_reopen_permit(root, binding, cycle_id)
    except OSError:
        _save_failed_binding(root, binding)
        transaction["state"] = "failed"
        save_mainline_reopen(root, transaction)
        raise
    transaction["state"] = "main_reopen_pending"
    save_mainline_reopen(root, transaction)
    return {
        "ok": True,
        "command": "reopen-node",
        "node_id": "main",
        "transaction_id": transaction["transaction_id"],
        "binding_id": binding["binding_id"],
        "permit_path": permit_path.resolve().as_posix(),
        "context_docs": result["decision"]["context_docs"],
        "context_snapshot": result["context_snapshot"],
        "frozen_ids": list(binding["frozen_nodes"]),
        "session_frozen": session_frozen,
        "shell_only": shell_only,
        "shell": shell,
        "next_steps": {
            "require": [
                f"DEC_REOPEN --permit {permit_path.resolve().as_posix()}",
                "GATE_CONTROL resolve-context",
                "load context_docs",
                "declare session switched",
            ]
        },
    }


def reopen_split(
    approach_root: Path,
    *,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> dict[str, Any]:
    """Freeze Working, bind Main as the Split parent anchor, and enter review."""
    root = Path(approach_root).resolve()
    transaction = _start_mainline_reopen(root, target="split")
    shell = load_shell(root)
    binding = _start_binding(root, "main", operation="enter")
    _, session_frozen, shell_only = _freeze_reopen_closure(
        root,
        target="split",
        closure=list((shell.get("by_id") or {}).keys()),
        binding=binding,
    )
    transaction["frozen"] = {
        "split": False,
        "nodes": list(binding["frozen_nodes"]),
    }
    transaction["state"] = "downstream_frozen"
    save_mainline_reopen(root, transaction)
    result = _bind_main(
        root,
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=constraints_path,
        binding=binding,
    )
    binding["state"] = "bound"
    save_node_binding(root, binding)
    shell = load_shell(root)
    shell["macro_state"] = "SplitReopen"
    shell["focus"] = "main"
    save_shell(root, shell)
    transaction["state"] = "split_pending"
    save_mainline_reopen(root, transaction)
    return {
        "ok": True,
        "command": "reopen-node",
        "node_id": "split",
        "transaction_id": transaction["transaction_id"],
        "binding_id": binding["binding_id"],
        "context_docs": result["decision"]["context_docs"],
        "context_snapshot": result["context_snapshot"],
        "frozen_ids": list(binding["frozen_nodes"]),
        "session_frozen": session_frozen,
        "shell_only": shell_only,
        "shell": shell,
        "next_steps": {
            "require": [
                "APPROACH_SHELL enter-node --node-id split",
                "generate a temporary C<n> candidate topology and C-to-D mapping",
                "human confirm the complete candidate before complete-split-reopen",
            ]
        },
    }


def reopen_node(
    approach_root: Path,
    node_id: str,
    *,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> dict[str, Any]:
    """Dispatch Main/Split/Dx reopen preparation to the correct protocol."""
    target = str(node_id).strip()
    if target == "main":
        return reopen_main(
            approach_root,
            project_root=project_root,
            cycle_id=cycle_id,
            constraints_path=constraints_path,
        )
    if target == "split":
        return reopen_split(
            approach_root,
            project_root=project_root,
            cycle_id=cycle_id,
            constraints_path=constraints_path,
        )
    return _reopen_dx(
        approach_root,
        target,
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=constraints_path,
    )


def complete_reopen(
    approach_root: Path,
    *,
    binding_id: str,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> dict[str, Any]:
    """Complete a consumed reopen permit after target RS has unfrozen its session."""
    del project_root, cycle_id, constraints_path
    root = Path(approach_root).resolve()
    binding = load_node_binding(root)
    if binding["binding_id"] != str(binding_id).strip():
        raise ValueError("complete-reopen binding-id does not match node-binding")
    if binding["state"] != "reopen_pending":
        raise ValueError(
            f"complete-reopen requires reopen_pending binding, got {binding['state']!r}"
        )
    permit_path = Path(str(binding.get("permit_path") or ""))
    if not permit_path.is_file():
        raise ValueError(f"complete-reopen permit missing: {permit_path}")
    permit = json.loads(permit_path.read_text(encoding="utf-8"))
    if (
        not isinstance(permit, dict)
        or permit.get("binding_id") != binding["binding_id"]
        or permit.get("state") != "consumed"
    ):
        raise ValueError("complete-reopen requires matching consumed permit")
    target = binding["target"]["node_id"]
    if _active_session_name(root) != target:
        raise ValueError("complete-reopen requires Active Session to remain the target")
    state = _parse_session_state_current(dx_session_dir(root, target) / _SESSION_STATE)
    if state is None or state == "Frozen":
        raise ValueError("complete-reopen requires target session to be non-Frozen")
    shell = load_shell(root)
    cell = dict((shell.get("by_id") or {}).get(target) or {})
    cell["frozen"] = False
    shell["by_id"][target] = cell
    save_shell(root, shell)
    binding["state"] = "bound"
    binding["permit_state"] = "consumed"
    save_node_binding(root, binding)
    return {
        "ok": True,
        "command": "complete-reopen",
        "binding_id": binding["binding_id"],
        "binding_state": binding["state"],
        "node_id": target,
        "shell": shell,
    }


def complete_main_reopen(
    approach_root: Path,
    *,
    transaction_id: str,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> dict[str, Any]:
    """Close Main reopen after its permit-backed decision repair completes."""
    del project_root, cycle_id, constraints_path
    root = Path(approach_root).resolve()
    transaction = load_mainline_reopen(root)
    if transaction["transaction_id"] != str(transaction_id).strip():
        raise ValueError("complete-main-reopen transaction-id does not match")
    if transaction["target"]["kind"] != "main":
        raise ValueError("complete-main-reopen requires a Main transaction")
    if transaction["state"] != "main_reopen_pending":
        raise ValueError(
            "complete-main-reopen requires main_reopen_pending transaction, "
            f"got {transaction['state']!r}"
        )
    binding = load_node_binding(root)
    if binding["target"]["node_id"] != "main" or binding["state"] != "reopen_pending":
        raise ValueError("complete-main-reopen requires pending Main node-binding")
    permit_path = Path(str(binding.get("permit_path") or ""))
    if not permit_path.is_file():
        raise ValueError(f"complete-main-reopen permit missing: {permit_path}")
    permit = json.loads(permit_path.read_text(encoding="utf-8"))
    if (
        not isinstance(permit, dict)
        or permit.get("binding_id") != binding["binding_id"]
        or permit.get("state") != "consumed"
    ):
        raise ValueError("complete-main-reopen requires matching consumed permit")
    if _active_session_name(root) != "main":
        raise ValueError("complete-main-reopen requires Active Session to remain Main")
    state = _parse_session_state_current(main_session_dir(root) / _SESSION_STATE)
    if state is None or state == "Frozen":
        raise ValueError("complete-main-reopen requires Main session to be non-Frozen")
    shell = load_shell(root)
    if shell["macro_state"] != "MainReopen":
        raise ValueError(
            f"complete-main-reopen requires macro_state=MainReopen, got {shell['macro_state']!r}"
        )
    shell["macro_state"] = "Main"
    shell["focus"] = "main"
    save_shell(root, shell)
    binding["state"] = "bound"
    binding["permit_state"] = "consumed"
    save_node_binding(root, binding)
    transaction["state"] = "main_repaired"
    save_mainline_reopen(root, transaction)
    return {
        "ok": True,
        "command": "complete-main-reopen",
        "transaction_id": transaction["transaction_id"],
        "state": transaction["state"],
        "shell": shell,
    }


def complete_split_reopen(
    approach_root: Path, *, transaction_id: str, confirm: bool
) -> dict[str, Any]:
    """Confirm a Split candidate and retain an identical frozen Working graph."""
    if not confirm:
        raise ValueError("complete-split-reopen blocked: human --confirm required")
    root = Path(approach_root).resolve()
    transaction = load_mainline_reopen(root)
    if transaction["transaction_id"] != str(transaction_id).strip():
        raise ValueError("complete-split-reopen transaction-id does not match")
    if transaction["state"] != "split_review":
        raise ValueError(
            "complete-split-reopen requires split_review transaction, "
            f"got {transaction['state']!r}"
        )
    candidate = load_candidate(root, transaction["transaction_id"])
    tree, rulers = materialize_candidate(candidate)
    old_signature = structure_signature(load_dependency_tree(root))
    candidate_signature = structure_signature(tree)
    transaction["structure_signature"] = {
        "old": old_signature,
        "candidate": candidate_signature,
    }
    if old_signature != candidate_signature:
        transaction["state"] = "archive_required"
        save_mainline_reopen(root, transaction)
        archive_working_generation(root, transaction["transaction_id"])
        save_dependency_tree(root, tree)
        save_decision_rulers(root, rulers)
        save_decision_package(
            root,
            build_decision_package(
                main=conventional_main_paths(),
                slices=slices_from_locked_tree(tree),
                status="split_delivered",
            ),
        )
        shell = load_shell(root)
        shell["by_id"] = {node["id"]: empty_cell() for node in tree["nodes"]}
        shell["macro_state"] = "SplitReopen"
        shell["focus"] = "main"
        shell["split_delivered"] = True
        save_shell(root, shell)
        transaction["state"] = "working_rebuilt"
        save_mainline_reopen(root, transaction)
        return {
            "ok": True,
            "command": "complete-split-reopen",
            "transaction_id": transaction["transaction_id"],
            "state": transaction["state"],
            "archive_path": (root / "working-archive" / transaction["transaction_id"]).as_posix(),
            "shell": shell,
        }
    save_dependency_tree(root, tree)
    save_decision_rulers(root, rulers)
    save_decision_package(
        root,
        build_decision_package(
            main=conventional_main_paths(),
            slices=slices_from_locked_tree(tree),
            status="split_delivered",
        ),
    )
    transaction["state"] = "working_retained"
    save_mainline_reopen(root, transaction)
    return {
        "ok": True,
        "command": "complete-split-reopen",
        "transaction_id": transaction["transaction_id"],
        "state": transaction["state"],
        "shell": load_shell(root),
    }


def _restore_previous_binding(
    approach_root: Path,
    binding: dict[str, Any],
    *,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> None:
    previous = binding["previous"]
    previous_session = previous.get("active_session")
    if previous_session:
        session_dir = _session_dir_for_node(approach_root, previous_session)
        snapshot = resolve_context.write_resolved_context(
            Path(project_root).resolve(),
            str(cycle_id).strip(),
            Path(constraints_path).resolve(),
            session_dir=session_dir,
            binding_id=binding["binding_id"],
        )
        bind_session(
            Path(project_root).resolve(),
            str(cycle_id).strip(),
            session_dir=session_dir,
            resolved_context_path=snapshot,
            mode="existing",
            constraints_path=Path(constraints_path).resolve(),
        )
    previous_focus = previous.get("focus")
    if previous_focus:
        force_commit_focus(approach_root, previous_focus)


def recover_binding(
    approach_root: Path,
    *,
    action: str,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> dict[str, Any]:
    """Recover a paused binding by commit, compensation, or explicit cancellation."""
    root = Path(approach_root).resolve()
    binding = load_node_binding(root)
    requested = str(action).strip()
    if requested not in {"commit-focus", "compensate-active", "cancel"}:
        raise ValueError(
            "recover-binding action must be commit-focus|compensate-active|cancel"
        )
    if requested == "commit-focus":
        if binding["state"] != "decision_bound":
            raise ValueError("recover-binding commit-focus requires decision_bound")
        shell = force_commit_focus(root, binding["target"]["node_id"])
        if binding["operation"] == "reopen":
            permit_path = _issue_reopen_permit(root, binding, cycle_id)
            state = "reopen_pending"
        else:
            binding["state"] = "bound"
            save_node_binding(root, binding)
            permit_path = None
            state = "bound"
        return {
            "ok": True,
            "command": "recover-binding",
            "action": requested,
            "binding_id": binding["binding_id"],
            "binding_state": state,
            "permit_path": None if permit_path is None else permit_path.as_posix(),
            "shell": shell,
        }

    _restore_previous_binding(
        root,
        binding,
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=constraints_path,
    )
    if requested == "cancel":
        shell = load_shell(root)
        by_id = dict(shell.get("by_id") or {})
        for node_id in binding["frozen_nodes"]:
            cell = dict(by_id.get(node_id) or empty_cell())
            cell["frozen"] = False
            by_id[node_id] = cell
            session_dir = dx_session_dir(root, node_id)
            if session_dir.is_dir():
                unfreeze_session_public(session_dir)
        shell["by_id"] = by_id
        save_shell(root, shell)
    path = node_binding_path(root)
    path.unlink(missing_ok=True)
    return {
        "ok": True,
        "command": "recover-binding",
        "action": requested,
        "binding_id": binding["binding_id"],
        "binding_cleared": True,
    }


def bind_check_frozen(approach_root: Path, node_id: str) -> dict[str, Any]:
    """After bind: signal realign_required; do not clear frozen (E6)."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    nid = str(node_id).strip()
    if not _DX_ID_RE.match(nid):
        raise ValueError(f"bind-check-frozen expects D<number>, got {nid!r}")
    cell = (shell.get("by_id") or {}).get(nid) or {}
    shell_frozen = isinstance(cell, dict) and cell.get("frozen") is True
    session_dir = dx_session_dir(root, nid)
    session_state = _parse_session_state_current(session_dir / _SESSION_STATE)
    session_frozen = session_state == "Frozen"
    required = shell_frozen or session_frozen
    return {
        "ok": True,
        "command": "bind-check-frozen",
        "node_id": nid,
        "realign_required": required,
        "shell_frozen": shell_frozen,
        "session_frozen": session_frozen,
        "cleared": False,
    }


def clear_frozen(approach_root: Path, node_id: str) -> dict[str, Any]:
    """Clear shell frozen (+ session Frozen) for one node after Realign / RS."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    nid = str(node_id).strip()
    if not _DX_ID_RE.match(nid):
        raise ValueError(f"clear-frozen expects D<number>, got {nid!r}")
    by_id = dict(shell.get("by_id") or {})
    if nid not in by_id:
        raise ValueError(f"clear-frozen unknown node {nid!r}")
    cell = dict(by_id[nid])
    cell["frozen"] = False
    by_id[nid] = cell
    shell["by_id"] = by_id
    save_shell(root, shell)
    session_unfroze = False
    dx = dx_session_dir(root, nid)
    if dx.is_dir() and (dx / _SESSION_STATE).is_file():
        session_unfroze = bool(unfreeze_session_public(dx))
    return {
        "ok": True,
        "command": "clear-frozen",
        "node_id": nid,
        "shell_frozen": False,
        "session_unfroze": session_unfroze,
        "shell": shell,
    }


def enter_package_ready(approach_root: Path) -> dict[str, Any]:
    """Main → PackageReady (no-split) or Working → PackageReady (all Dx Delivered)."""
    shell = load_shell(approach_root)
    macro = shell["macro_state"]
    if macro == "Main":
        if not is_node_delivered(approach_root, "main", shell):
            raise ValueError("enter_package_ready blocked: main is not Completed")
        shell["macro_state"] = "PackageReady"
        shell["focus"] = "main"
        save_shell(approach_root, shell)
        return shell
    if macro == "Working":
        by_id = shell.get("by_id") or {}
        if not by_id:
            raise ValueError("enter_package_ready blocked: empty by_id")
        frozen = _frozen_ids(shell)
        if frozen:
            raise ValueError(
                "enter_package_ready blocked: frozen nodes present: "
                + ", ".join(frozen)
            )
        incomplete = [
            nid
            for nid, cell in by_id.items()
            if not (
                cell.get("delivered") is True
                or is_node_delivered(approach_root, nid, shell)
            )
        ]
        if incomplete:
            raise ValueError(
                "enter_package_ready blocked: not all children Completed "
                f"(pending/frozen: {', '.join(incomplete)})"
            )
        shell["macro_state"] = "PackageReady"
        save_shell(approach_root, shell)
        return shell
    raise ValueError(
        f"enter_package_ready requires Main or Working, got {macro!r}"
    )


def _restore_file(path: Path, previous: bytes | None) -> None:
    if previous is None:
        path.unlink(missing_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(previous)


def deliver(
    approach_root: Path,
    *,
    confirm: bool,
    cycle_id: str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Stage deliver at PackageReady; ensure decision-package; register refs."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    if shell["macro_state"] != "PackageReady":
        raise ValueError(
            f"deliver requires macro_state=PackageReady, got {shell['macro_state']!r}"
        )
    frozen = _frozen_ids(shell)
    if frozen:
        raise ValueError(
            "deliver blocked: frozen nodes present: " + ", ".join(frozen)
        )
    if not confirm:
        raise ValueError("deliver blocked: human --confirm required")
    cid = str(cycle_id or "").strip()
    if not cid:
        raise ValueError("deliver requires --cycle-id")
    if project_root is None:
        raise ValueError("deliver requires --project-root")
    proj = Path(project_root).resolve()

    decision_pkg_path = decision_package_path(root)
    if not decision_pkg_path.is_file():
        write_early_package(root)
    load_decision_package(decision_pkg_path)

    refs_path = delivered_refs_file_path(cid, proj)
    refs_before = refs_path.read_bytes() if refs_path.is_file() else None
    residual_source = source_package_path(root)

    source = str(shell_path(root).resolve())
    try:
        record_delivered_ref(
            cid,
            proj,
            delivered_type="lulu-approach",
            path=str(decision_pkg_path.resolve()),
            artifact="decision-package",
            revision=1,
            profile_id="lulu-approach",
            source_workflow_state=source,
        )
        residual_source.unlink(missing_ok=True)
    except Exception:
        # Keep existing decision-package; only roll back delivered-refs.
        _restore_file(refs_path, refs_before)
        raise
    return {
        "ok": True,
        "macro_state": "PackageReady",
        "delivered": True,
        "decision_package": str(decision_pkg_path.resolve()),
        "source_workflow_state": source,
    }


def confirm_seal(
    approach_root: Path,
    *,
    confirm: bool,
    cycle_id: str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Deprecated alias for ``deliver`` (stage Deliver)."""
    return deliver(
        approach_root,
        confirm=confirm,
        cycle_id=cycle_id,
        project_root=project_root,
    )


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
        prog="approach_shell_control.py",
        description="Approach outer-shell control (Main/Split/Working/PackageReady).",
    )
    p.add_argument("--approach-root", required=True, type=Path)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init-shell", help="Create layout + Main shell pointer")

    sub.add_parser("enter-split", help="Main → Split (main must be Delivered)")

    p_ew = sub.add_parser("enter-working", help="Split → Working")
    p_ew.add_argument("--node-ids", nargs="+", required=True)
    p_ew.add_argument("--focus", default=None)

    p_sf = sub.add_parser("set-focus", help="Retired; use enter-node")
    p_sf.add_argument("--node-id", required=True)

    p_en = sub.add_parser(
        "enter-node",
        help="Bind context, Active Session, and Working focus for one Dx",
    )
    p_en.add_argument("--node-id", required=True)
    p_en.add_argument("--project-root", required=True, type=Path)
    p_en.add_argument("--cycle-id", required=True)
    p_en.add_argument("--constraints", required=True, type=Path)
    p_en.add_argument("--force", action="store_true")

    p_fc = sub.add_parser(
        "freeze-cascade",
        help="Freeze node + DAG successors (shell + session)",
    )
    p_fc.add_argument("--node-id", required=True)

    p_rn = sub.add_parser(
        "reopen-node",
        help="Freeze reopen closure, bind target, and issue a reopen permit",
    )
    p_rn.add_argument("--node-id", required=True)
    p_rn.add_argument("--project-root", required=True, type=Path)
    p_rn.add_argument("--cycle-id", required=True)
    p_rn.add_argument("--constraints", required=True, type=Path)

    p_cr = sub.add_parser(
        "complete-reopen",
        help="Finish a consumed reopen permit after target RS",
    )
    p_cr.add_argument("--binding-id", required=True)
    p_cr.add_argument("--project-root", required=True, type=Path)
    p_cr.add_argument("--cycle-id", required=True)
    p_cr.add_argument("--constraints", required=True, type=Path)

    p_cmr = sub.add_parser(
        "complete-main-reopen",
        help="Finish a consumed Main reopen permit after RS",
    )
    p_cmr.add_argument("--transaction-id", required=True)
    p_cmr.add_argument("--project-root", required=True, type=Path)
    p_cmr.add_argument("--cycle-id", required=True)
    p_cmr.add_argument("--constraints", required=True, type=Path)

    p_csr = sub.add_parser(
        "complete-split-reopen",
        help="Confirm a Split candidate and retain or rebuild Working",
    )
    p_csr.add_argument("--transaction-id", required=True)
    p_csr.add_argument("--confirm", action="store_true")

    p_rb = sub.add_parser(
        "recover-binding",
        help="Recover a paused node-binding transaction",
    )
    p_rb.add_argument(
        "--action",
        required=True,
        choices=["commit-focus", "compensate-active", "cancel"],
    )
    p_rb.add_argument("--project-root", required=True, type=Path)
    p_rb.add_argument("--cycle-id", required=True)
    p_rb.add_argument("--constraints", required=True, type=Path)

    p_bc = sub.add_parser(
        "bind-check-frozen",
        help="After bind: emit realign_required without clearing frozen",
    )
    p_bc.add_argument("--node-id", required=True)

    p_cf = sub.add_parser(
        "clear-frozen",
        help="Clear shell/session frozen for one node after Realign",
    )
    p_cf.add_argument("--node-id", required=True)

    sub.add_parser(
        "enter-package-ready",
        help="Main/Working → PackageReady",
    )

    for cmd_name, help_text in (
        ("deliver", "Stage deliver + delivered-refs (decision-package)"),
        ("confirm-seal", "Deprecated alias for deliver"),
    ):
        p_cs = sub.add_parser(cmd_name, help=help_text)
        p_cs.add_argument("--confirm", action="store_true")
        p_cs.add_argument("--cycle-id", required=True)
        p_cs.add_argument("--project-root", required=True, type=Path)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    root = Path(args.approach_root).resolve()
    try:
        if args.command == "init-shell":
            return _emit_ok({"shell": init_shell(root)})
        if args.command == "enter-split":
            return _emit_ok({"shell": enter_split(root)})
        if args.command == "enter-working":
            return _emit_ok(
                {
                    "shell": enter_working(
                        root, list(args.node_ids), focus=args.focus
                    )
                }
            )
        if args.command == "set-focus":
            return _emit_ok({"shell": set_focus(root, args.node_id)})
        if args.command == "enter-node":
            return _emit_ok(
                enter_node(
                    root,
                    args.node_id,
                    project_root=Path(args.project_root),
                    cycle_id=args.cycle_id,
                    constraints_path=Path(args.constraints),
                    force=bool(args.force),
                )
            )
        if args.command == "freeze-cascade":
            return _emit_ok(freeze_cascade(root, args.node_id))
        if args.command == "reopen-node":
            return _emit_ok(
                reopen_node(
                    root,
                    args.node_id,
                    project_root=Path(args.project_root),
                    cycle_id=args.cycle_id,
                    constraints_path=Path(args.constraints),
                )
            )
        if args.command == "complete-reopen":
            return _emit_ok(
                complete_reopen(
                    root,
                    binding_id=args.binding_id,
                    project_root=Path(args.project_root),
                    cycle_id=args.cycle_id,
                    constraints_path=Path(args.constraints),
                )
            )
        if args.command == "complete-main-reopen":
            return _emit_ok(
                complete_main_reopen(
                    root,
                    transaction_id=args.transaction_id,
                    project_root=Path(args.project_root),
                    cycle_id=args.cycle_id,
                    constraints_path=Path(args.constraints),
                )
            )
        if args.command == "complete-split-reopen":
            return _emit_ok(
                complete_split_reopen(
                    root,
                    transaction_id=args.transaction_id,
                    confirm=bool(args.confirm),
                )
            )
        if args.command == "recover-binding":
            return _emit_ok(
                recover_binding(
                    root,
                    action=args.action,
                    project_root=Path(args.project_root),
                    cycle_id=args.cycle_id,
                    constraints_path=Path(args.constraints),
                )
            )
        if args.command == "bind-check-frozen":
            return _emit_ok(bind_check_frozen(root, args.node_id))
        if args.command == "clear-frozen":
            return _emit_ok(clear_frozen(root, args.node_id))
        if args.command == "enter-package-ready":
            return _emit_ok({"shell": enter_package_ready(root)})
        if args.command in {"deliver", "confirm-seal"}:
            return _emit_ok(
                deliver(
                    root,
                    confirm=bool(args.confirm),
                    cycle_id=args.cycle_id,
                    project_root=Path(args.project_root),
                )
            )
    except (FileNotFoundError, ValueError, OSError) as exc:
        return _emit_err(str(exc))
    return _emit_err(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
