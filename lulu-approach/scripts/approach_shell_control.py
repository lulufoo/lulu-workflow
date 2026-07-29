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
enter-package-ready, confirm-seal.
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
_WORKFLOW_SCRIPTS = _SCRIPTS.parents[1] / "scripts"
for _p in (_SCRIPTS, _SCHEMA, _WORKFLOW_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

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
        ensure_dx_on_focus(approach_root, target)
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
    ensure_dx_on_focus(approach_root, target)
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
