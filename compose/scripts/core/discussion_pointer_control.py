#!/usr/bin/env python3
"""L-slice control (multi-subdesign v1.1) — ``$L_SLICE``.

Subcommands:
    status              Show focus / ready / by_id / advisory phase
    resume              Continue current focus (no state change)
    ready               List DAG-ready node ids (EnterPolicy)
    can-admit           Check EnterPolicy for ``--to``
    can-enter-evaluate  Check StageGate for focus (or ``--to``)
    switch              Change focus via EnterPolicy (--confirm)
    mark-done           Mark focus mature for ``--kind`` inductive|production
    demote-production   Set target production→pending (+ FreeEdit sync if focus)
    seam-report         Advisory Boundary seam checklist

Illegal transitions hard-reject with unchanged on-disk focus state.
v1.0 pointer/frontier/phase on disk are rejected (no compatibility).
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
_SECTION = _SCRIPTS / "section"
for _p in (_HERE, _SESSION, _SECTION, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dependency_tree_schema import load_dependency_tree  # noqa: E402
from discussion_pointer_schema import (  # noqa: E402
    active_ids,
    can_admit,
    can_enter_evaluate,
    focus_phase,
    load_discussion_pointer,
    ready_ids,
    save_discussion_pointer,
    slice_past_init,
)
from workflow_common import parse_frontmatter_fields  # noqa: E402

_BOUNDARY_HEADING = "## Boundary"
_DRAFTING_PROGRESS = "drafting-progress.md"


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


def _sync_drafting_for_focus(revision_dir: Path, node_id: str, pointer: dict[str, Any]) -> str | None:
    """Align revision ``drafting-progress.md`` with target L maturity (best-effort).

    Returns the step written, or None when no progress file existed and L is
    still inductive-pending (absent progress is valid for begin-inductive).
    """
    path = Path(revision_dir) / _DRAFTING_PROGRESS
    cell = pointer["by_id"][node_id]
    if cell["inductive"] != "done":
        step = "Inductive"
    elif cell["production"] == "done":
        step = "FreeEdit"
    elif slice_past_init(revision_dir, node_id):
        step = "FreeEdit"
    else:
        step = "Inductive"

    cycle_id = "unknown"
    if path.is_file():
        fields = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
        cycle_id = str(fields.get("cycle_id") or cycle_id).strip() or "unknown"
    elif step == "Inductive" and cell["inductive"] != "done":
        return None

    path.write_text(
        f"---\nversion: 1\ncycle_id: {cycle_id}\ncurrent_step: {step}\n---\n",
        encoding="utf-8",
    )
    return step


def _status_payload(
    revision_dir: Path,
    tree: dict[str, Any],
    pointer: dict[str, Any],
    *,
    command: str,
) -> dict[str, Any]:
    focus = str(pointer["focus"])
    return {
        "ok": True,
        "command": command,
        "revision_dir": Path(revision_dir).as_posix(),
        "focus": focus,
        "active": active_ids(pointer),
        "ready": ready_ids(tree, pointer),
        "phase": focus_phase(pointer, focus),  # advisory only; not persisted
        "by_id": pointer["by_id"],
        "node_ids": list(tree.get("order") or []),  # inventory; not a push order
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
    """Continue work at current focus; does not mutate pointer state."""
    try:
        tree, pointer = _load(revision_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    _emit(_status_payload(revision_dir, tree, pointer, command="resume"))
    return 0


def cmd_ready(revision_dir: Path) -> int:
    try:
        tree, pointer = _load(revision_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    ready = ready_ids(tree, pointer)
    _emit(
        {
            **_status_payload(revision_dir, tree, pointer, command="ready"),
            "ready": ready,
        }
    )
    return 0


def cmd_can_admit(revision_dir: Path, *, target: str) -> int:
    try:
        tree, pointer = _load(revision_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    ok, reason = can_admit(tree, pointer, str(target).strip())
    payload = {
        **_status_payload(revision_dir, tree, pointer, command="can-admit"),
        "target": str(target).strip(),
        "admit": ok,
    }
    if reason:
        payload["reason"] = reason
    _emit(payload)
    return 0 if ok else 1


def cmd_can_enter_evaluate(revision_dir: Path, *, target: str | None) -> int:
    try:
        tree, pointer = _load(revision_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    nid = str(target).strip() if target else str(pointer["focus"])
    ok, reason = can_enter_evaluate(tree, pointer, nid)
    payload = {
        **_status_payload(revision_dir, tree, pointer, command="can-enter-evaluate"),
        "target": nid,
        "enter_evaluate": ok,
    }
    if reason:
        payload["reason"] = reason
    _emit(payload)
    return 0 if ok else 1


def cmd_switch(revision_dir: Path, *, target: str, confirm: bool) -> int:
    err = _require_confirm(confirm)
    if err:
        return _emit_error(err)
    try:
        tree, pointer = _load(revision_dir)
        tgt = str(target).strip()
        ok, reason = can_admit(tree, pointer, tgt)
        if not ok:
            return _emit_error(reason or f"cannot admit {tgt!r}")
        pointer["focus"] = tgt
        save_discussion_pointer(revision_dir, pointer, tree=tree)
        drafting_step = _sync_drafting_for_focus(revision_dir, tgt, pointer)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return _emit_error(str(exc))
    payload = _status_payload(revision_dir, tree, pointer, command="switch")
    if drafting_step is not None:
        payload["drafting_step"] = drafting_step
    _emit(payload)
    return 0


def cmd_mark_done(
    revision_dir: Path,
    *,
    confirm: bool,
    kind: str | None,
) -> int:
    err = _require_confirm(confirm)
    if err:
        return _emit_error(err)
    try:
        tree, pointer = _load(revision_dir)
        cur = str(pointer["focus"])
        cell = pointer["by_id"][cur]
        if kind:
            phase = str(kind).strip()
            if phase not in ("inductive", "production"):
                return _emit_error("kind must be inductive|production")
        else:
            phase = "inductive" if cell["inductive"] != "done" else "production"
        if phase == "production":
            gate_errs = _production_exit_errors(revision_dir, cur)
            if gate_errs:
                return _emit_error("; ".join(gate_errs))
            if cell["inductive"] != "done":
                return _emit_error(
                    f"cannot mark production done: {cur!r} inductive is not done"
                )
        if cell[phase] == "done":
            _emit(
                {
                    **_status_payload(revision_dir, tree, pointer, command="mark-done"),
                    "noop": True,
                    "kind": phase,
                }
            )
            return 0
        cell[phase] = "done"
        save_discussion_pointer(revision_dir, pointer, tree=tree)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return _emit_error(str(exc))
    payload = _status_payload(revision_dir, tree, pointer, command="mark-done")
    payload["kind"] = phase
    _emit(payload)
    return 0


def cmd_demote_production(
    revision_dir: Path,
    *,
    target: str,
    confirm: bool,
) -> int:
    """Bucket side-effect: production→pending; FreeEdit sync when target is focus."""
    err = _require_confirm(confirm)
    if err:
        return _emit_error(err)
    try:
        tree, pointer = _load(revision_dir)
        tgt = str(target).strip()
        if tgt not in pointer["by_id"]:
            return _emit_error(f"unknown target {tgt!r}")
        cell = pointer["by_id"][tgt]
        was_done = cell["production"] == "done"
        demoted = False
        if was_done:
            cell["production"] = "pending"
            demoted = True
        drafting_step = None
        if demoted and str(pointer["focus"]) == tgt:
            drafting_step = _sync_drafting_for_focus(revision_dir, tgt, pointer)
        if demoted:
            save_discussion_pointer(revision_dir, pointer, tree=tree)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return _emit_error(str(exc))
    payload = _status_payload(revision_dir, tree, pointer, command="demote-production")
    payload["target"] = tgt
    payload["demoted"] = demoted
    payload["was_production_done"] = was_done
    if drafting_step is not None:
        payload["drafting_step"] = drafting_step
    _emit(payload)
    return 0


def cmd_seam_report(revision_dir: Path) -> int:
    try:
        payload = seam_report(revision_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    _emit(payload)
    return 0


def stage_gate_for_revision(revision_dir: Path) -> tuple[bool, str | None]:
    """Library helper for Evaluating entry. No pointer file → skip (single-slice)."""
    from discussion_pointer_schema import discussion_pointer_path

    rev = Path(revision_dir).resolve()
    if not discussion_pointer_path(rev).is_file():
        return True, None
    try:
        tree, pointer = _load(rev)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return False, str(exc)
    focus = str(pointer["focus"])
    return can_enter_evaluate(tree, pointer, focus)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="L-slice control ($L_SLICE) — multi-subdesign v1.1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--revision-dir",
        required=True,
        type=Path,
        help="Path to revision{N}/ directory",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show focus / ready / active / by_id")
    sub.add_parser("resume", help="Resume current focus (no state change)")
    sub.add_parser("ready", help="List DAG-ready nodes (EnterPolicy)")
    sub.add_parser("seam-report", help="Advisory Boundary seam checklist")

    p_admit = sub.add_parser("can-admit", help="Check EnterPolicy for a node")
    p_admit.add_argument("--to", required=True, dest="target", help="Node id e.g. L2")

    p_eval = sub.add_parser(
        "can-enter-evaluate",
        help="Check StageGate (deps production done)",
    )
    p_eval.add_argument(
        "--to",
        dest="target",
        default=None,
        help="Node id (default: current focus)",
    )

    p_sw = sub.add_parser("switch", help="Change focus (EnterPolicy + --confirm)")
    p_sw.add_argument("--to", required=True, dest="target", help="Node id e.g. L2")
    p_sw.add_argument("--confirm", action="store_true")

    p_mark = sub.add_parser("mark-done", help="Mark focus mature for a kind")
    p_mark.add_argument(
        "--kind",
        choices=("inductive", "production"),
        default=None,
        help="Default: inductive if pending else production",
    )
    p_mark.add_argument("--confirm", action="store_true")

    p_dem = sub.add_parser(
        "demote-production",
        help="Set target production→pending (bucket write side-effect)",
    )
    p_dem.add_argument("--to", required=True, dest="target")
    p_dem.add_argument("--confirm", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    rev = args.revision_dir.resolve()
    if args.command == "status":
        return cmd_status(rev)
    if args.command == "resume":
        return cmd_resume(rev)
    if args.command == "ready":
        return cmd_ready(rev)
    if args.command == "seam-report":
        return cmd_seam_report(rev)
    if args.command == "can-admit":
        return cmd_can_admit(rev, target=args.target)
    if args.command == "can-enter-evaluate":
        return cmd_can_enter_evaluate(rev, target=args.target)
    if args.command == "switch":
        return cmd_switch(rev, target=args.target, confirm=bool(args.confirm))
    if args.command == "mark-done":
        return cmd_mark_done(rev, confirm=bool(args.confirm), kind=args.kind)
    if args.command == "demote-production":
        return cmd_demote_production(
            rev, target=args.target, confirm=bool(args.confirm)
        )
    return _emit_error(f"unknown command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
