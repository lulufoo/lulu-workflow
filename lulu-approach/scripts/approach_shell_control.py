#!/usr/bin/env python3
"""Approach outer-shell control (archive-1.0 P2.shell).

Macro transitions::

    Main → Split → Working → PackageReady
    Main → PackageReady          (no-split shortcut)

Working: single focus; reject mid-switch until current focus is Delivered.
PackageReady: human ``confirm_seal`` required before seal (no auto-seal).

Delivered stub: prefer ``by_id[].delivered``; else ``session-state.md``
``current_state: Delivered`` under ``main/`` or ``Dx/`` when present.

CLI (stdout JSON ``{"ok": true, ...}``; errors on stderr, exit 1)::

    python3 approach_shell_control.py --approach-root <path> <subcommand> ...

Subcommands: init-shell, enter-split, enter-working, set-focus,
enter-package-ready, confirm-seal, freeze-cascade, reopen-node,
bind-check-frozen, clear-frozen.
"""

from __future__ import annotations

import argparse
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

from approach_dependency_tree_schema import load_dependency_tree  # noqa: E402
from approach_layout import (  # noqa: E402
    decision_package_path,
    dx_session_dir,
    ensure_approach_layout,
    main_session_dir,
)
from approach_shell_schema import (  # noqa: E402
    empty_cell,
    initial_shell,
    load_shell,
    save_shell,
    shell_path,
)
from approach_split_control import write_early_package  # noqa: E402
from cycle_delivered_refs import record_delivered_ref  # noqa: E402
from decision_package_schema import load_decision_package  # noqa: E402
from dec_session_state_schema import (  # noqa: E402
    set_session_frozen,
    unfreeze_session,
)

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
    """True when node is effectively Delivered (delivered ∧ ¬frozen)."""
    nid = str(node_id).strip()
    data = shell if shell is not None else load_shell(approach_root)
    if nid != "main":
        cell = (data.get("by_id") or {}).get(nid)
        if isinstance(cell, dict) and cell.get("frozen") is True:
            return False
        if isinstance(cell, dict) and cell.get("delivered") is True:
            return True
    session_dir = _session_dir_for_node(approach_root, nid)
    state = _parse_session_state_current(session_dir / _SESSION_STATE)
    if state == "Frozen":
        return False
    return state == "Delivered"


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
        raise ValueError("enter_split blocked: main is not Delivered")
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
        raise ValueError("enter_working blocked: Split is not Delivered")
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
                "RESOLVE_CONTEXT with --session-dir",
                "DEC_START or DEC_SET_ACTIVE with --session-dir and --domain-constraints-file",
                "GATE_CONTROL resolve-context",
                "load context_docs",
                "declare session switched",
            ],
        },
    }


def set_focus(approach_root: Path, node_id: str) -> dict[str, Any]:
    """Switch Working focus. Rejects mid-switch until current focus is Delivered."""
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
            f"focus switch blocked: current focus {current!r} is not Delivered"
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
        set_session_frozen(session_dir)
        return "session_frozen"
    return "skipped"


def _bind_next_steps(session_dir: Path) -> dict[str, Any]:
    return {
        "session_dir": session_dir.as_posix(),
        "require": [
            "RESOLVE_CONTEXT with --session-dir",
            "DEC_START or DEC_SET_ACTIVE with --session-dir and --domain-constraints-file",
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


def _force_focus(approach_root: Path, node_id: str) -> dict[str, Any]:
    """Set Working focus without requiring current focus Delivered."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    if shell["macro_state"] != "Working":
        raise ValueError(
            f"force focus requires macro_state=Working, got {shell['macro_state']!r}"
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


def reopen_node(approach_root: Path, node_id: str) -> dict[str, Any]:
    """Cascade-freeze target+successors and force focus onto target (F6)."""
    root = Path(approach_root).resolve()
    frozen = freeze_cascade(root, node_id)
    shell = _force_focus(root, node_id)
    return {
        "ok": True,
        "command": "reopen-node",
        "node_id": str(node_id).strip(),
        "frozen_ids": frozen["frozen_ids"],
        "session_frozen": frozen["session_frozen"],
        "shell_only": frozen["shell_only"],
        "shell": shell,
        "next_steps": shell.get("next_steps"),
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
        session_unfroze = bool(unfreeze_session(dx))
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
            raise ValueError("enter_package_ready blocked: main is not Delivered")
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
                "enter_package_ready blocked: not all children Delivered "
                f"(pending/frozen: {', '.join(incomplete)})"
            )
        shell["macro_state"] = "PackageReady"
        save_shell(approach_root, shell)
        return shell
    raise ValueError(
        f"enter_package_ready requires Main or Working, got {macro!r}"
    )


def confirm_seal(
    approach_root: Path,
    *,
    confirm: bool,
    cycle_id: str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Human confirm at PackageReady; ensure package; register delivered-refs."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    if shell["macro_state"] != "PackageReady":
        raise ValueError(
            f"confirm_seal requires macro_state=PackageReady, got {shell['macro_state']!r}"
        )
    frozen = _frozen_ids(shell)
    if frozen:
        raise ValueError(
            "confirm_seal blocked: frozen nodes present: " + ", ".join(frozen)
        )
    if not confirm:
        raise ValueError("confirm_seal blocked: human --confirm required")
    cid = str(cycle_id or "").strip()
    if not cid:
        raise ValueError("confirm_seal requires --cycle-id")
    if project_root is None:
        raise ValueError("confirm_seal requires --project-root")
    proj = Path(project_root).resolve()

    pkg_path = decision_package_path(root)
    if not pkg_path.is_file():
        write_early_package(root)
    else:
        package = load_decision_package(pkg_path)
        slices = package.get("slices") or []
        if slices:
            missing: list[str] = []
            for row in slices:
                sid = str(row.get("id", "")).strip()
                for key in ("decision_fact_path", "decision_doc_path"):
                    rel = str(row.get(key, "")).strip()
                    target = (root / rel).resolve()
                    try:
                        target.relative_to(root)
                    except ValueError as exc:
                        raise ValueError(
                            f"confirm_seal blocked: slice {sid!r} {key} escapes root: {rel!r}"
                        ) from exc
                    if not target.is_file():
                        missing.append(f"{sid}:{key}={rel}")
            if missing:
                raise ValueError(
                    "confirm_seal blocked: missing slice artifact(s): "
                    + ", ".join(missing)
                )

    source = str(shell_path(root).resolve())
    record_delivered_ref(
        cid,
        proj,
        delivered_type="lulu-approach",
        path=str(pkg_path.resolve()),
        artifact="decision-package",
        revision=1,
        profile_id="lulu-approach",
        source_workflow_state=source,
    )
    return {
        "ok": True,
        "macro_state": "PackageReady",
        "sealed": True,
        "decision_package": str(pkg_path.resolve()),
        "source_workflow_state": source,
    }


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

    p_sf = sub.add_parser("set-focus", help="Switch Working focus")
    p_sf.add_argument("--node-id", required=True)

    p_fc = sub.add_parser(
        "freeze-cascade",
        help="Freeze node + DAG successors (shell + session)",
    )
    p_fc.add_argument("--node-id", required=True)

    p_rn = sub.add_parser(
        "reopen-node",
        help="Cascade-freeze + force focus onto node (reopen bypass)",
    )
    p_rn.add_argument("--node-id", required=True)

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

    p_cs = sub.add_parser("confirm-seal", help="Human confirm + delivered-refs")
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
        if args.command == "freeze-cascade":
            return _emit_ok(freeze_cascade(root, args.node_id))
        if args.command == "reopen-node":
            return _emit_ok(reopen_node(root, args.node_id))
        if args.command == "bind-check-frozen":
            return _emit_ok(bind_check_frozen(root, args.node_id))
        if args.command == "clear-frozen":
            return _emit_ok(clear_frozen(root, args.node_id))
        if args.command == "enter-package-ready":
            return _emit_ok({"shell": enter_package_ready(root)})
        if args.command == "confirm-seal":
            return _emit_ok(
                confirm_seal(
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
