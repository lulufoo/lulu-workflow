#!/usr/bin/env python3
"""Approach outer-shell control (archive-1.0 P2.shell).

Macro transitions::

    Main → Split → Working → PackageReady
    Main → PackageReady          (no-split shortcut)

Working: single focus; reject mid-switch until current focus is Delivered.
PackageReady: human ``confirm_seal`` required before seal (no auto-seal).

Delivered stub: prefer ``by_id[].delivered``; else ``session-state.md``
``current_state: Delivered`` under ``main/`` or ``Dx/`` when present.
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
    main_session_dir,
)
from approach_shell_schema import (  # noqa: E402
    empty_cell,
    initial_shell,
    load_shell,
    save_shell,
)

_DX_ID_RE = re.compile(r"^D\d+$")
_SESSION_STATE = "session-state.md"


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
    """True when node is Delivered (by_id flag and/or session-state stub)."""
    nid = str(node_id).strip()
    data = shell if shell is not None else load_shell(approach_root)
    if nid != "main":
        cell = (data.get("by_id") or {}).get(nid)
        if isinstance(cell, dict) and cell.get("delivered") is True:
            return True
        if isinstance(cell, dict) and cell.get("frozen") is True:
            return False
    session_dir = _session_dir_for_node(approach_root, nid)
    state = _parse_session_state_current(session_dir / _SESSION_STATE)
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
    """Stub: mark Split phase complete (P2.split owns the real cut)."""
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
    ensure_approach_layout(approach_root, dx_ids=ids)
    by_id = {nid: empty_cell(phase="pending") for nid in ids}
    by_id[focus_id] = empty_cell(phase="in_progress")
    shell["macro_state"] = "Working"
    shell["focus"] = focus_id
    shell["by_id"] = by_id
    save_shell(approach_root, shell)
    return shell


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
        return shell
    if current is not None and not is_node_delivered(approach_root, str(current), shell):
        raise ValueError(
            f"focus switch blocked: current focus {current!r} is not Delivered"
        )
    if by_id[target].get("frozen") is True:
        raise ValueError(f"focus switch blocked: {target!r} is Frozen")
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
    return shell


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
        incomplete = [
            nid
            for nid, cell in by_id.items()
            if not (
                cell.get("delivered") is True
                or is_node_delivered(approach_root, nid, shell)
            )
            or cell.get("frozen") is True
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


def confirm_seal(approach_root: Path, *, confirm: bool) -> dict[str, Any]:
    """Human confirm at PackageReady. Does not auto-seal; returns ok payload."""
    shell = load_shell(approach_root)
    if shell["macro_state"] != "PackageReady":
        raise ValueError(
            f"confirm_seal requires macro_state=PackageReady, got {shell['macro_state']!r}"
        )
    if not confirm:
        raise ValueError("confirm_seal blocked: human --confirm required")
    return {
        "ok": True,
        "macro_state": "PackageReady",
        "sealed": True,
        "message": "human confirmed seal; register delivered-refs to decision-package",
    }
