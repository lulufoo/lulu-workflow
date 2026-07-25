#!/usr/bin/env python3
"""Discussion pointer control (multi-subdesign MVP).

Subcommands:
    status         Show pointer / frontier / phase / by_id
    resume         Continue current pointer (no state change)
    mark-done      Mark current pointer mature for active phase (--confirm)
    advance        Move pointer+frontier to next in order (--confirm)
    backtrack      Move pointer to an earlier/equal id ≤ frontier (--confirm)
    phase-switch   inductive → production after all inductive done (--confirm)

Illegal transitions hard-reject with unchanged on-disk state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
_SESSION = _SCRIPTS / "schema" / "session"
for _p in (_HERE, _SESSION, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dependency_tree_schema import load_dependency_tree  # noqa: E402
from discussion_pointer_schema import (  # noqa: E402
    deps_of,
    load_discussion_pointer,
    order_index,
    save_discussion_pointer,
)

_BOUNDARY_HEADING = "## Boundary"


def _production_exit_errors(revision_dir: Path, node_id: str) -> list[str]:
    """Structural production exit: design-doc.md with ``## Boundary`` (may be empty)."""
    doc = Path(revision_dir) / node_id / "design-doc.md"
    if not doc.is_file():
        return [f"missing {doc.as_posix()}"]
    text = doc.read_text(encoding="utf-8")
    if _BOUNDARY_HEADING not in text:
        return [f"{doc.as_posix()} missing {_BOUNDARY_HEADING!r} section"]
    return []


def seam_report(revision_dir: Path) -> dict[str, Any]:
    """Checklist seam report from edges vs Boundary headings (advisory, never hard-fail)."""
    tree = load_dependency_tree(revision_dir)
    findings: list[dict[str, Any]] = []
    for edge in tree.get("edges") or []:
        frm = str(edge.get("from", ""))
        to = str(edge.get("to", ""))
        from_doc = Path(revision_dir) / frm / "design-doc.md"
        to_doc = Path(revision_dir) / to / "design-doc.md"
        from_text = from_doc.read_text(encoding="utf-8") if from_doc.is_file() else ""
        to_text = to_doc.read_text(encoding="utf-8") if to_doc.is_file() else ""
        findings.append(
            {
                "edge": {"from": frm, "to": to},
                "from_has_boundary": _BOUNDARY_HEADING in from_text,
                "to_has_boundary": _BOUNDARY_HEADING in to_text,
                "note": (
                    f"Human: confirm {frm} Boundary declares dependency on {to}, "
                    f"and {to} Boundary supplies it"
                ),
            }
        )
    return {
        "ok": True,
        "command": "seam-report",
        "hard_reject": False,
        "edges_checked": len(findings),
        "findings": findings,
    }


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _emit_error(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    return 1


def _require_confirm(confirm: bool) -> str | None:
    if not confirm:
        return "human --confirm required"
    return None


def _load(revision_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    tree = load_dependency_tree(revision_dir)
    if tree.get("status") != "locked":
        raise ValueError("dependency tree must be status=locked")
    pointer = load_discussion_pointer(revision_dir)
    return tree, pointer


def _status_payload(
    revision_dir: Path,
    tree: dict[str, Any],
    pointer: dict[str, Any],
    *,
    command: str,
) -> dict[str, Any]:
    return {
        "ok": True,
        "command": command,
        "revision_dir": Path(revision_dir).as_posix(),
        "phase": pointer["phase"],
        "pointer": pointer["pointer"],
        "frontier": pointer["frontier"],
        "by_id": pointer["by_id"],
        "order": list(tree.get("order") or []),
        "tree_status": tree.get("status"),
    }


def cmd_status(revision_dir: Path) -> int:
    try:
        tree, pointer = _load(revision_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    _emit(_status_payload(revision_dir, tree, pointer, command="status"))
    return 0


def cmd_resume(revision_dir: Path) -> int:
    """Continue work at current pointer; does not mutate pointer state."""
    try:
        tree, pointer = _load(revision_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    _emit(_status_payload(revision_dir, tree, pointer, command="resume"))
    return 0


def cmd_mark_done(revision_dir: Path, *, confirm: bool) -> int:
    err = _require_confirm(confirm)
    if err:
        return _emit_error(err)
    try:
        tree, pointer = _load(revision_dir)
        phase = str(pointer["phase"])
        cur = str(pointer["pointer"])
        if phase == "production":
            gate_errs = _production_exit_errors(revision_dir, cur)
            if gate_errs:
                return _emit_error("; ".join(gate_errs))
        cell = pointer["by_id"][cur]
        if cell[phase] == "done":
            _emit(
                {
                    **_status_payload(revision_dir, tree, pointer, command="mark-done"),
                    "noop": True,
                }
            )
            return 0
        cell[phase] = "done"
        save_discussion_pointer(revision_dir, pointer, tree=tree)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return _emit_error(str(exc))
    _emit(_status_payload(revision_dir, tree, pointer, command="mark-done"))
    return 0


def cmd_seam_report(revision_dir: Path) -> int:
    try:
        payload = seam_report(revision_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    _emit(payload)
    return 0


def cmd_advance(revision_dir: Path, *, confirm: bool) -> int:
    err = _require_confirm(confirm)
    if err:
        return _emit_error(err)
    try:
        tree, pointer = _load(revision_dir)
        phase = str(pointer["phase"])
        order = list(tree["order"])
        cur = str(pointer["pointer"])
        if pointer["by_id"][cur][phase] != "done":
            return _emit_error(
                f"current {cur!r} phase={phase} is not done; mark-done first"
            )
        idx = order_index(tree, cur)
        if idx >= len(order) - 1:
            return _emit_error("already at last node in order; use phase-switch if ready")
        nxt = order[idx + 1]
        for dep in deps_of(tree, nxt):
            if pointer["by_id"][dep][phase] != "done":
                return _emit_error(
                    f"cannot advance to {nxt!r}: dependency {dep!r} "
                    f"phase={phase} is not done"
                )
        pointer["pointer"] = nxt
        pointer["frontier"] = nxt
        save_discussion_pointer(revision_dir, pointer, tree=tree)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return _emit_error(str(exc))
    _emit(_status_payload(revision_dir, tree, pointer, command="advance"))
    return 0


def cmd_backtrack(revision_dir: Path, *, target: str, confirm: bool) -> int:
    err = _require_confirm(confirm)
    if err:
        return _emit_error(err)
    try:
        tree, pointer = _load(revision_dir)
        tgt = str(target).strip()
        order = list(tree["order"])
        if tgt not in order:
            return _emit_error(f"unknown target {tgt!r}")
        if order_index(tree, tgt) > order_index(tree, str(pointer["frontier"])):
            return _emit_error(
                f"cannot move pointer to {tgt!r}: past frontier "
                f"{pointer['frontier']!r}"
            )
        pointer["pointer"] = tgt
        # frontier and by_id unchanged
        save_discussion_pointer(revision_dir, pointer, tree=tree)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return _emit_error(str(exc))
    _emit(_status_payload(revision_dir, tree, pointer, command="backtrack"))
    return 0


def cmd_phase_switch(revision_dir: Path, *, confirm: bool) -> int:
    err = _require_confirm(confirm)
    if err:
        return _emit_error(err)
    try:
        tree, pointer = _load(revision_dir)
        if pointer["phase"] != "inductive":
            return _emit_error("phase-switch only from inductive → production")
        incomplete = [
            nid
            for nid in tree["order"]
            if pointer["by_id"][nid]["inductive"] != "done"
        ]
        if incomplete:
            return _emit_error(
                "not all nodes inductive=done: " + ", ".join(incomplete)
            )
        first = list(tree["order"])[0]
        pointer["phase"] = "production"
        pointer["pointer"] = first
        pointer["frontier"] = first
        save_discussion_pointer(revision_dir, pointer, tree=tree)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return _emit_error(str(exc))
    _emit(_status_payload(revision_dir, tree, pointer, command="phase-switch"))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discussion pointer control (multi-subdesign MVP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--revision-dir",
        required=True,
        type=Path,
        help="Path to revision{N}/ directory",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show pointer state")
    sub.add_parser("resume", help="Resume current pointer (no state change)")
    sub.add_parser("seam-report", help="Advisory Boundary seam checklist (no hard reject)")

    p_mark = sub.add_parser("mark-done", help="Mark current L mature for active phase")
    p_mark.add_argument("--confirm", action="store_true")

    p_adv = sub.add_parser("advance", help="Advance pointer and frontier")
    p_adv.add_argument("--confirm", action="store_true")

    p_bt = sub.add_parser("backtrack", help="Move pointer backward (≤ frontier)")
    p_bt.add_argument("--target", required=True, help="Node id e.g. L1")
    p_bt.add_argument("--confirm", action="store_true")

    p_ps = sub.add_parser("phase-switch", help="Switch inductive → production")
    p_ps.add_argument("--confirm", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    rev = args.revision_dir.resolve()
    if args.command == "status":
        return cmd_status(rev)
    if args.command == "resume":
        return cmd_resume(rev)
    if args.command == "seam-report":
        return cmd_seam_report(rev)
    if args.command == "mark-done":
        return cmd_mark_done(rev, confirm=bool(args.confirm))
    if args.command == "advance":
        return cmd_advance(rev, confirm=bool(args.confirm))
    if args.command == "backtrack":
        return cmd_backtrack(rev, target=args.target, confirm=bool(args.confirm))
    if args.command == "phase-switch":
        return cmd_phase_switch(rev, confirm=bool(args.confirm))
    return _emit_error(f"unknown command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
