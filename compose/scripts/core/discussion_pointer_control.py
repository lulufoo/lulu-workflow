#!/usr/bin/env python3
"""L-slice control — ``$L_SLICE``.

Subcommands:
    status              Show focus / ready / by_id / phase
    resume              Continue current focus (no state change)
    ready               List DAG-ready node ids (EnterPolicy)
    can-admit           Check EnterPolicy for ``--to``
    can-enter-evaluate  Check StageGate for focus (or ``--to``)
    switch              Change focus via EnterPolicy (--confirm)
    mark-done           Mark focus mature for ``--kind`` intake|acceptance
                        (acceptance requires phase=evaluating; prefer accept-l)
    accept-l            Accept focus L (evaluating→accepted); optional --switch
    fix-l               Focus evaluating→in_progress (--confirm)
    demote-acceptance   Set target acceptance→pending (+ FreeEdit sync if focus)
    seam-report         Advisory Boundary seam checklist

Illegal transitions hard-reject with unchanged on-disk focus state.
Root-level ``phase`` is forbidden (v1.0); per-L ``by_id.*.phase`` is required.
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
_SCHEMA_SECTION = _SCRIPTS / "schema" / "section"
_SECTION = _SCRIPTS / "section"
for _p in (_HERE, _SESSION, _SCHEMA_SECTION, _SECTION, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dependency_tree_schema import load_dependency_tree  # noqa: E402
from discussion_pointer_schema import (  # noqa: E402
    active_ids,
    all_l_accepted,
    can_admit,
    can_enter_evaluate,
    focus_phase,
    load_discussion_pointer,
    ready_ids,
    save_discussion_pointer,
    slice_past_init,
    suggested_next_l,
)
from l_step_progress_schema import allowed_steps, save_l_step_progress  # noqa: E402
from multi_slice_control import document_filename_for_profile  # noqa: E402
from workflow_common import parse_frontmatter_fields  # noqa: E402
from workflow_paths import resolve_profile_id  # noqa: E402

_BOUNDARY_HEADING = "## Boundary"
_L_STEP_PROGRESS = "l-step-progress.md"


def _acceptance_exit_errors(
    revision_dir: Path,
    node_id: str,
    *,
    doc_filename: str,
) -> list[str]:
    """Structural acceptance exit: profile doc with ``## Boundary`` (may be empty)."""
    doc = Path(revision_dir) / node_id / doc_filename
    if not doc.is_file():
        return [f"missing {doc.as_posix()}"]
    text = doc.read_text(encoding="utf-8")
    if _BOUNDARY_HEADING not in text:
        return [f"{doc.as_posix()} missing {_BOUNDARY_HEADING!r} section"]
    return []


def seam_report(revision_dir: Path, *, doc_filename: str) -> dict[str, Any]:
    """Checklist seam report from edges vs Boundary headings (advisory, never hard-fail)."""
    tree = load_dependency_tree(revision_dir)
    findings: list[dict[str, Any]] = []
    for edge in tree.get("edges") or []:
        frm = str(edge.get("from", ""))
        to = str(edge.get("to", ""))
        from_doc = Path(revision_dir) / frm / doc_filename
        to_doc = Path(revision_dir) / to / doc_filename
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


def _sync_l_step_for_focus(
    revision_dir: Path,
    node_id: str,
    pointer: dict[str, Any],
    *,
    profile_id: str,
) -> str | None:
    """Align revision ``l-step-progress.md`` with target L maturity (best-effort).

    Writes only via ``l_step_progress_schema.save_l_step_progress`` so
    ``allowed_steps()`` is enforced. Returns the step written, or None when no
    progress file existed and L is still intake-pending (absent progress is
    valid for begin-inductive / begin-deductive).
    """
    path = Path(revision_dir) / _L_STEP_PROGRESS
    cell = pointer["by_id"][node_id]
    pid = profile_id.strip()
    allowed = allowed_steps(pid)
    phase = str(cell.get("phase") or "pending")
    if phase in ("pending", "in_progress") and cell["intake"] != "done":
        step = "Inductive"
    elif phase == "accepted" or cell["acceptance"] == "done" or slice_past_init(
        revision_dir, node_id
    ):
        if "FreeEdit" in allowed:
            step = "FreeEdit"
        elif "Written" in allowed:
            step = "Written"
        else:
            step = "Inductive"
    else:
        step = "Inductive"

    if step not in allowed:
        # Profile has no Inductive (deductive-only): map to Deductive when needed.
        if "Deductive" in allowed and step == "Inductive":
            step = "Deductive"
        elif step not in allowed:
            step = next(iter(sorted(allowed)))

    cycle_id = "unknown"
    if path.is_file():
        fields = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
        cycle_id = str(fields.get("cycle_id") or cycle_id).strip() or "unknown"
    elif step in ("Inductive", "Deductive") and cell.get("phase") in (
        "pending",
        "in_progress",
    ) and cell["intake"] != "done":
        return None

    save_l_step_progress(
        path,
        {"version": "1", "cycle_id": cycle_id, "current_step": step},
        profile_id=pid,
        merge=False,
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


def cmd_switch(
    revision_dir: Path,
    *,
    target: str,
    confirm: bool,
    profile_id: str,
) -> int:
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
        l_step = _sync_l_step_for_focus(
            revision_dir, tgt, pointer, profile_id=profile_id
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return _emit_error(str(exc))
    payload = _status_payload(revision_dir, tree, pointer, command="switch")
    if l_step is not None:
        payload["l_step"] = l_step
    _emit(payload)
    return 0


def cmd_mark_done(
    revision_dir: Path,
    *,
    confirm: bool,
    kind: str | None,
    profile_id: str,
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
            if phase not in ("intake", "acceptance"):
                return _emit_error("kind must be intake|acceptance")
        else:
            phase = "intake" if cell["intake"] != "done" else "acceptance"
        if phase == "acceptance":
            if cell.get("phase") != "evaluating":
                return _emit_error(
                    f"cannot mark acceptance done: focus {cur!r} phase is "
                    f"{cell.get('phase')!r} (expected evaluating); use accept-l"
                )
            doc_filename = document_filename_for_profile(profile_id)
            gate_errs = _acceptance_exit_errors(
                revision_dir, cur, doc_filename=doc_filename
            )
            if gate_errs:
                return _emit_error("; ".join(gate_errs))
            if cell["intake"] != "done":
                return _emit_error(
                    f"cannot mark acceptance done: {cur!r} intake is not done"
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
        if phase == "intake" and cell.get("phase") == "pending":
            cell["phase"] = "in_progress"
        if phase == "acceptance":
            cell["phase"] = "accepted"
        save_discussion_pointer(revision_dir, pointer, tree=tree)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return _emit_error(str(exc))
    payload = _status_payload(revision_dir, tree, pointer, command="mark-done")
    payload["kind"] = phase
    _emit(payload)
    return 0


def cmd_demote_acceptance(
    revision_dir: Path,
    *,
    target: str,
    confirm: bool,
    profile_id: str = "",
) -> int:
    """Bucket side-effect: acceptance→pending; FreeEdit sync when target is focus.

    L-step-progress sync runs only when ``profile_id`` is non-empty (CLI always
    passes ``--profile``; library callers such as facts write may omit it).
    """
    err = _require_confirm(confirm)
    if err:
        return _emit_error(err)
    try:
        tree, pointer = _load(revision_dir)
        tgt = str(target).strip()
        if tgt not in pointer["by_id"]:
            return _emit_error(f"unknown target {tgt!r}")
        cell = pointer["by_id"][tgt]
        was_done = cell["acceptance"] == "done"
        demoted = False
        if was_done:
            cell["acceptance"] = "pending"
            cell["phase"] = "in_progress"
            demoted = True
        l_step = None
        pid = profile_id.strip()
        if demoted and str(pointer["focus"]) == tgt and pid:
            l_step = _sync_l_step_for_focus(
                revision_dir, tgt, pointer, profile_id=pid
            )
        if demoted:
            save_discussion_pointer(revision_dir, pointer, tree=tree)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return _emit_error(str(exc))
    payload = _status_payload(revision_dir, tree, pointer, command="demote-acceptance")
    payload["target"] = tgt
    payload["demoted"] = demoted
    payload["was_acceptance_done"] = was_done
    if l_step is not None:
        payload["l_step"] = l_step
    _emit(payload)
    return 0


def cmd_accept_l(
    revision_dir: Path,
    *,
    confirm: bool,
    switch: bool,
    profile_id: str,
) -> int:
    """Accept focus L (evaluating→accepted). Optional --switch to suggested next."""
    err = _require_confirm(confirm)
    if err:
        return _emit_error(err)
    try:
        tree, pointer = _load(revision_dir)
        cur = str(pointer["focus"])
        cell = pointer["by_id"][cur]
        if cell.get("phase") != "evaluating":
            return _emit_error(
                f"cannot accept-l: focus {cur!r} phase is "
                f"{cell.get('phase')!r} (expected evaluating)"
            )
        doc_filename = document_filename_for_profile(profile_id)
        gate_errs = _acceptance_exit_errors(
            revision_dir, cur, doc_filename=doc_filename
        )
        if gate_errs:
            return _emit_error("; ".join(gate_errs))
        if cell.get("intake") != "done":
            return _emit_error(f"cannot accept-l: {cur!r} intake is not done")
        cell["acceptance"] = "done"
        cell["phase"] = "accepted"
        save_discussion_pointer(revision_dir, pointer, tree=tree)
        suggested = suggested_next_l(tree, pointer, after_id=cur)
        switched_to = None
        if switch:
            if not suggested:
                return _emit_error(
                    "cannot --switch: no suggested next L "
                    "(all remaining blocked or all accepted)"
                )
            ok, reason = can_admit(tree, pointer, suggested)
            if not ok:
                return _emit_error(reason or f"cannot admit {suggested!r}")
            pointer["focus"] = suggested
            if pointer["by_id"][suggested].get("phase") == "pending":
                pointer["by_id"][suggested]["phase"] = "in_progress"
            save_discussion_pointer(revision_dir, pointer, tree=tree)
            switched_to = suggested
            _sync_l_step_for_focus(
                revision_dir, suggested, pointer, profile_id=profile_id
            )
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return _emit_error(str(exc))
    payload = _status_payload(revision_dir, tree, pointer, command="accept-l")
    payload["accepted"] = cur
    payload["suggested_next"] = suggested
    payload["all_accepted"] = all_l_accepted(pointer)
    payload["switched_to"] = switched_to
    _emit(payload)
    return 0


def cmd_fix_l(
    revision_dir: Path,
    *,
    confirm: bool,
    profile_id: str,
) -> int:
    """Focus evaluating → in_progress (Fix L)."""
    err = _require_confirm(confirm)
    if err:
        return _emit_error(err)
    try:
        tree, pointer = _load(revision_dir)
        cur = str(pointer["focus"])
        cell = pointer["by_id"][cur]
        if cell.get("phase") != "evaluating":
            return _emit_error(
                f"cannot fix-l: focus {cur!r} phase is "
                f"{cell.get('phase')!r} (expected evaluating)"
            )
        cell["phase"] = "in_progress"
        cell["acceptance"] = "pending"
        save_discussion_pointer(revision_dir, pointer, tree=tree)
        l_step = _sync_l_step_for_focus(
            revision_dir, cur, pointer, profile_id=profile_id
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return _emit_error(str(exc))
    payload = _status_payload(revision_dir, tree, pointer, command="fix-l")
    payload["focus"] = cur
    if l_step is not None:
        payload["l_step"] = l_step
    _emit(payload)
    return 0


def cmd_seam_report(revision_dir: Path, *, profile_id: str) -> int:
    try:
        doc_filename = document_filename_for_profile(profile_id)
        payload = seam_report(revision_dir, doc_filename=doc_filename)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    _emit(payload)
    return 0


def stage_gate_for_revision(revision_dir: Path) -> tuple[bool, str | None]:
    """Library helper for evaluating entry. No pointer file → skip (single-slice)."""
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
    parser.add_argument(
        "--profile",
        default="",
        help="Compose profile / stage id (default: cycle context after start)",
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
        help="Check StageGate (deps acceptance done)",
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
        choices=("intake", "acceptance"),
        default=None,
        help="Default: intake if pending else acceptance",
    )
    p_mark.add_argument("--confirm", action="store_true")

    p_dem = sub.add_parser(
        "demote-acceptance",
        help="Set target acceptance→pending (bucket write side-effect)",
    )
    p_dem.add_argument("--to", required=True, dest="target")
    p_dem.add_argument("--confirm", action="store_true")

    p_acc = sub.add_parser(
        "accept-l",
        help="Accept focus L; optional --switch to suggested next ready L",
    )
    p_acc.add_argument("--confirm", action="store_true")
    p_acc.add_argument(
        "--switch",
        action="store_true",
        help="After accept, switch to suggested_next (human confirm)",
    )

    p_fix = sub.add_parser("fix-l", help="Focus evaluating→in_progress (Fix L)")
    p_fix.add_argument("--confirm", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    rev = args.revision_dir.resolve()
    try:
        profile_id = resolve_profile_id(
            revision_dir=rev,
            explicit=args.profile,
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    if args.command == "status":
        return cmd_status(rev)
    if args.command == "resume":
        return cmd_resume(rev)
    if args.command == "ready":
        return cmd_ready(rev)
    if args.command == "seam-report":
        return cmd_seam_report(rev, profile_id=profile_id)
    if args.command == "can-admit":
        return cmd_can_admit(rev, target=args.target)
    if args.command == "can-enter-evaluate":
        return cmd_can_enter_evaluate(rev, target=args.target)
    if args.command == "switch":
        return cmd_switch(
            rev,
            target=args.target,
            confirm=bool(args.confirm),
            profile_id=profile_id,
        )
    if args.command == "mark-done":
        return cmd_mark_done(
            rev,
            confirm=bool(args.confirm),
            kind=args.kind,
            profile_id=profile_id,
        )
    if args.command == "demote-acceptance":
        return cmd_demote_acceptance(
            rev,
            target=args.target,
            confirm=bool(args.confirm),
            profile_id=profile_id,
        )
    if args.command == "accept-l":
        return cmd_accept_l(
            rev,
            confirm=bool(args.confirm),
            switch=bool(args.switch),
            profile_id=profile_id,
        )
    if args.command == "fix-l":
        return cmd_fix_l(
            rev,
            confirm=bool(args.confirm),
            profile_id=profile_id,
        )
    return _emit_error(f"unknown command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
