#!/usr/bin/env python3
"""Draft control for product-spec orchestrator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts"
_SECTION = _KERNEL_SCRIPTS / "section"
_DRAFTING = Path(__file__).resolve().parent
_START = _DRAFTING.parent / "start"
for p in (_KERNEL_SCRIPTS, _KERNEL_SCRIPTS / "core", _SECTION, _DRAFTING, _START):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_profile_context import set_active_profile  # noqa: E402
from product_spec_drafting_progress_schema import (  # noqa: E402
    PROFILE_ID,
    load_drafting_progress,
    read_current_step,
    resolve_drafting_progress_path_from_cycle,
    save_drafting_progress,
)
from section_round_control import init_round_dir_if_needed  # noqa: E402
from session_state_schema import load_active_doc  # noqa: E402
from workflow_common import CACHE_DIR, detect_cycle_type  # noqa: E402
from product_spec_start_adapter import ProductSpecStartAdapter  # noqa: E402
from workflow_profile_paths import (  # noqa: E402
    doc_dir,
    document_path,
    session_state_path,
)

_CMD_BEGIN_INIT = "begin-init"
_CMD_INIT_COMPLETE = "init-complete"
_CMD_BEGIN_ROUND = "begin-round"
_CMD_ADVANCE_ROUND = "advance-round"
_CMD_ADVANCE_TO_FREEEDIT = "advance-to-freeedit"
_CMD_STATUS = "status"
_STEP_READY = "Ready"
_STEP_ROUND = "RoundIteration"
_STEP_FREE_EDIT = "FreeEdit"


def _active_doc(cycle_id: str, project_root: Path) -> int:
    return load_active_doc(
        project_root / session_state_path(cycle_id, PROFILE_ID),
        default=1,
    )


def _cycle_dir(cycle_id: str, project_root: Path) -> Path:
    return (project_root / CACHE_DIR / cycle_id).resolve()


def _ensure_round_dir(cycle_id: str, project_root: Path, *, round_n: int) -> None:
    set_active_profile(PROFILE_ID)
    cycle_dir = _cycle_dir(cycle_id, project_root)
    if not cycle_dir.exists():
        return
    try:
        init_round_dir_if_needed(cycle_dir, round_n=round_n)
    except FileNotFoundError:
        return


def _product_doc_path(cycle_id: str, project_root: Path) -> Path:
    return project_root / document_path(
        cycle_id,
        _active_doc(cycle_id, project_root),
        PROFILE_ID,
    )


def _success(command: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "command": command}
    payload.update(extra)
    return payload


def _failure(command: str, reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "command": command, "reason": reason}
    payload.update(extra)
    return payload


def _format_init_dispatch_input(
    *,
    revision_dir: Path,
    decision_doc: Path,
    output_doc: Path,
    cycle_type: str,
    cycle_id: str,
) -> str:
    lines = [
        f"REVISION_DIR:         {revision_dir.resolve().as_posix()}",
        f"DECISION_DOC_PATH:    {decision_doc.resolve().as_posix()}",
        f"OUTPUT_DOC_PATH:      {output_doc.resolve().as_posix()}",
        f"COMPOSE_PROFILE:      {PROFILE_ID}",
        f"CYCLE_TYPE:           {cycle_type}",
        f"CYCLE_ID:             {cycle_id}",
    ]
    return "\n".join(lines)


def _init_dispatch_input(cycle_id: str, project_root: Path) -> str:
    active_doc = _active_doc(cycle_id, project_root)
    revision_dir = project_root / doc_dir(cycle_id, active_doc, PROFILE_ID)
    output_doc = project_root / document_path(cycle_id, active_doc, PROFILE_ID)
    adapter = ProductSpecStartAdapter()
    init_ref = adapter.delivered_ref_for_init(cycle_id, project_root)
    if init_ref is None:
        raise ValueError("no delivered ref available for Initializing")
    return _format_init_dispatch_input(
        revision_dir=revision_dir,
        decision_doc=Path(init_ref.path),
        output_doc=output_doc,
        cycle_type=detect_cycle_type(cycle_id),
        cycle_id=cycle_id,
    )


def _section_order_for_profile(project_root: Path) -> list[str]:
    from fetch_compose_framework import fetch_compose_framework  # noqa: WPS433

    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=PROFILE_ID,
    )
    data = json.loads(raw)
    return [str(key) for key in data.get("section_order", [])]


def _validate_product_doc_seeded(product_doc: Path, project_root: Path) -> str | None:
    if not product_doc.exists():
        return f"compose document not found: {product_doc}"
    from compose_doc_schema import section_body_by_key  # noqa: WPS433

    raw = product_doc.read_text(encoding="utf-8")
    empty: list[str] = []
    for key in _section_order_for_profile(project_root):
        body = section_body_by_key(raw, key).strip()
        if not body:
            empty.append(key)
    if empty:
        return f"compose document sections with empty body: {', '.join(empty)}"
    return None


def begin_init(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    dispatch_input = _init_dispatch_input(cycle_id, project_root)
    if not progress_path.exists():
        return _success(
            _CMD_BEGIN_INIT,
            current_step=None,
            dispatch_input=dispatch_input,
        )

    step = read_current_step(progress_path)
    if step == _STEP_READY:
        return _success(
            _CMD_BEGIN_INIT,
            current_step=_STEP_READY,
            dispatch_input=dispatch_input,
        )

    return _failure(
        _CMD_BEGIN_INIT,
        f"cannot start Initializing: current_step is {step!r} (expected absent or Ready)",
        current_step=step,
    )


def init_complete(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    product_doc = _product_doc_path(cycle_id, project_root)

    seed_error = _validate_product_doc_seeded(product_doc, project_root)
    if seed_error:
        return _failure(_CMD_INIT_COMPLETE, seed_error)

    if progress_path.exists():
        step = read_current_step(progress_path)
        if step not in (None, _STEP_READY):
            return _failure(
                _CMD_INIT_COMPLETE,
                f"drafting-progress already at {step!r}; cannot re-initialize",
                current_step=step,
            )
        existing = load_drafting_progress(progress_path)
        if (
            existing.get("current_step") == _STEP_READY
            and existing.get("cycle_id") == cycle_id
        ):
            return _success(
                _CMD_INIT_COMPLETE,
                current_step=_STEP_READY,
                product_doc=product_doc.resolve().as_posix(),
            )

    save_drafting_progress(
        progress_path,
        {
            "version": "1",
            "cycle_id": cycle_id,
            "current_step": _STEP_READY,
        },
        merge=False,
    )
    return _success(
        _CMD_INIT_COMPLETE,
        current_step=_STEP_READY,
        product_doc=product_doc.resolve().as_posix(),
    )


def begin_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    if not progress_path.exists():
        return _failure(
            _CMD_BEGIN_ROUND,
            "drafting-progress.md not found; run init-complete first",
        )

    step = read_current_step(progress_path)
    if step == _STEP_ROUND:
        data = load_drafting_progress(progress_path)
        round_n = max(1, int(data.get("round", "1")))
        _ensure_round_dir(cycle_id, project_root, round_n=round_n)
        return _success(
            _CMD_BEGIN_ROUND,
            current_step=_STEP_ROUND,
            round=round_n,
        )

    if step != _STEP_READY:
        return _failure(
            _CMD_BEGIN_ROUND,
            f"cannot begin round: current_step is {step!r} (expected Ready)",
            current_step=step,
        )

    save_drafting_progress(
        progress_path,
        {
            "version": "1",
            "cycle_id": cycle_id,
            "current_step": _STEP_ROUND,
            "round": "1",
        },
        merge=False,
    )
    _ensure_round_dir(cycle_id, project_root, round_n=1)
    return _success(_CMD_BEGIN_ROUND, current_step=_STEP_ROUND, round=1)


def advance_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    if not progress_path.exists():
        return _failure(
            _CMD_ADVANCE_ROUND,
            "drafting-progress.md not found; run begin-round first",
        )

    data = load_drafting_progress(progress_path)
    step = data.get("current_step")
    if step != _STEP_ROUND:
        return _failure(
            _CMD_ADVANCE_ROUND,
            f"cannot advance round: current_step is {step!r} (expected RoundIteration)",
            current_step=step,
        )

    current_round = max(1, int(data.get("round", "1")))
    new_round = current_round + 1
    save_drafting_progress(
        progress_path,
        {
            "version": "1",
            "cycle_id": data.get("cycle_id", cycle_id),
            "current_step": _STEP_ROUND,
            "round": str(new_round),
        },
        merge=False,
    )
    _ensure_round_dir(cycle_id, project_root, round_n=new_round)
    return _success(_CMD_ADVANCE_ROUND, current_step=_STEP_ROUND, round=new_round)


def advance_to_freeedit(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    if not progress_path.exists():
        return _failure(
            _CMD_ADVANCE_TO_FREEEDIT,
            "drafting-progress.md not found; run begin-round first",
        )

    data = load_drafting_progress(progress_path)
    step = data.get("current_step")
    if step == _STEP_FREE_EDIT:
        return _success(_CMD_ADVANCE_TO_FREEEDIT, current_step=_STEP_FREE_EDIT)

    if step != _STEP_ROUND:
        return _failure(
            _CMD_ADVANCE_TO_FREEEDIT,
            f"cannot advance to FreeEdit: current_step is {step!r} (expected RoundIteration)",
            current_step=step,
        )

    payload: dict[str, str] = {
        "version": "1",
        "cycle_id": data.get("cycle_id", cycle_id),
        "current_step": _STEP_FREE_EDIT,
    }
    if data.get("round"):
        payload["round"] = data["round"]
    save_drafting_progress(progress_path, payload, merge=False)
    return _success(_CMD_ADVANCE_TO_FREEEDIT, current_step=_STEP_FREE_EDIT)


def draft_status(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    if not progress_path.exists():
        return _failure(_CMD_STATUS, "drafting-progress.md not found")
    data = load_drafting_progress(progress_path)
    result: dict[str, Any] = {
        "current_step": data.get("current_step"),
        "cycle_id": data.get("cycle_id"),
    }
    if data.get("round"):
        result["round"] = int(data["round"])
    return _success(_CMD_STATUS, **result)


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _cli() -> int:
    parser = argparse.ArgumentParser(description="product-spec draft control")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root directory",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(_CMD_BEGIN_INIT, help="Begin Initializing (gate + dispatch input)")
    sub.add_parser(_CMD_INIT_COMPLETE, help="Complete Initializing")
    sub.add_parser(_CMD_BEGIN_ROUND, help="Begin Round Iteration")
    sub.add_parser(_CMD_ADVANCE_ROUND, help="Increment round counter")
    sub.add_parser(_CMD_ADVANCE_TO_FREEEDIT, help="Transition to FreeEdit")
    sub.add_parser(_CMD_STATUS, help="Read drafting-progress snapshot")

    args = parser.parse_args()
    project_root = args.project_root.resolve()
    cycle_id = args.cycle_id.strip()

    try:
        if args.command == _CMD_BEGIN_INIT:
            result = begin_init(cycle_id, project_root)
            if result.get("ok"):
                print(result["dispatch_input"])
                return 0
            return _emit(result)
        if args.command == _CMD_INIT_COMPLETE:
            return _emit(init_complete(cycle_id, project_root))
        if args.command == _CMD_BEGIN_ROUND:
            return _emit(begin_round(cycle_id, project_root))
        if args.command == _CMD_ADVANCE_ROUND:
            return _emit(advance_round(cycle_id, project_root))
        if args.command == _CMD_ADVANCE_TO_FREEEDIT:
            return _emit(advance_to_freeedit(cycle_id, project_root))
        if args.command == _CMD_STATUS:
            return _emit(draft_status(cycle_id, project_root))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
