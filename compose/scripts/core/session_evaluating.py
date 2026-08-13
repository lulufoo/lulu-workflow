"""Enter per-L evaluating sub-state while session stays Working."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_CORE = Path(__file__).resolve().parent
_SCRIPTS = _CORE.parent
_SESSION = _SCRIPTS / "schema" / "session"
for _p in (_CORE, _SESSION, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_session import workflow_state_path  # noqa: E402
from discussion_pointer_control import stage_gate_for_revision  # noqa: E402
from discussion_pointer_schema import (  # noqa: E402
    load_discussion_pointer,
    save_discussion_pointer,
)
from dependency_tree_schema import load_dependency_tree  # noqa: E402
from multi_slice_control import evaluate_split_ready  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID  # noqa: E402
from workflow_profile_paths import eval_layout_for_revision  # noqa: E402
from workflow_state_schema import load_workflow_state, save_workflow_state  # noqa: E402


def _read_evaluate_round_field(path: Path) -> int | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("evaluate_round:"):
            raw = line.split(":", 1)[1].strip()
            try:
                return int(raw)
            except ValueError:
                return None
    return None


def _allocate_per_l_round(slice_dir: Path) -> int:
    es_path = slice_dir / "evaluate-state.md"
    if not es_path.is_file():
        return 1
    status = ""
    for line in es_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("eval_status:"):
            status = line.split(":", 1)[1].strip()
            break
    current = _read_evaluate_round_field(es_path) or 1
    if status in {"done", "abandoned"}:
        return current + 1
    return current if current >= 1 else 1


def enter_evaluating_state(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Set focus L ``phase=evaluating``; session remains ``Working``.

    Requires locked Split topology. Multi-L StageGate: every dependency of the
    current focus must have ``acceptance: done``. Focus must already have
    ``intake: done``.
    """
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current != "Working":
        return {
            "ok": False,
            "current_state": current,
            "transitioned": False,
            "resume": {
                "entry": current,
                "action": f"当前状态是 {current}，需要 Working 才能开始评估当前 L。",
            },
        }

    revision_dir = ws_path.parent
    topo_ok, topo_err, _ = evaluate_split_ready(revision_dir)
    if not topo_ok:
        return {
            "ok": False,
            "current_state": current,
            "transitioned": False,
            "error": topo_err or "split topology not ready",
            "resume": {
                "entry": current,
                "action": (
                    "无 locked 拓扑，不能进入 L evaluating；Blocking，请新开 revision。"
                    f" ({topo_err})"
                ),
            },
        }

    gate_ok, gate_reason = stage_gate_for_revision(revision_dir)
    if not gate_ok:
        return {
            "ok": False,
            "current_state": current,
            "transitioned": False,
            "error": gate_reason or "StageGate blocked evaluating entry",
            "resume": {
                "entry": current,
                "action": (
                    "StageGate: 前置 L 尚未 acceptance=done，不能进入 evaluating。"
                    f" ({gate_reason})"
                ),
            },
        }

    try:
        tree = load_dependency_tree(revision_dir)
        pointer = load_discussion_pointer(revision_dir)
    except (FileNotFoundError, ValueError, OSError) as exc:
        return {
            "ok": False,
            "current_state": current,
            "transitioned": False,
            "error": str(exc),
            "resume": {"entry": current, "action": str(exc)},
        }

    focus = str(pointer["focus"])
    cell = pointer["by_id"][focus]
    layout = eval_layout_for_revision(revision_dir)
    if cell.get("phase") == "evaluating":
        if layout == "legacy-root":
            try:
                evaluate_round = int(state.get("evaluate_round", "0"))
            except ValueError:
                evaluate_round = 0
        else:
            evaluate_round = _allocate_per_l_round(revision_dir / focus)
        return {
            "ok": True,
            "current_state": "Working",
            "focus": focus,
            "phase": "evaluating",
            "evaluate_round": evaluate_round,
            "layout": layout,
            "transitioned": False,
        }

    if cell.get("intake") != "done":
        return {
            "ok": False,
            "current_state": current,
            "transitioned": False,
            "error": f"focus {focus!r} intake is not done",
            "resume": {
                "entry": current,
                "action": f"当前 L {focus} 尚未 intake=done，不能进入 evaluating。",
            },
        }
    if cell.get("phase") == "accepted":
        return {
            "ok": False,
            "current_state": current,
            "transitioned": False,
            "error": f"focus {focus!r} already accepted",
            "resume": {
                "entry": current,
                "action": f"当前 L {focus} 已 accepted；请 switch 到其它 L 或交付。",
            },
        }

    cell["phase"] = "evaluating"
    cell["acceptance"] = "pending"
    try:
        save_discussion_pointer(revision_dir, pointer, tree=tree)
    except ValueError as exc:
        return {
            "ok": False,
            "current_state": current,
            "transitioned": False,
            "error": str(exc),
            "resume": {"entry": current, "action": str(exc)},
        }

    merged = dict(state)
    merged["current_state"] = "Working"
    if layout == "legacy-root":
        try:
            evaluate_round = int(state.get("evaluate_round", "0")) + 1
        except ValueError:
            evaluate_round = 1
        merged["evaluate_round"] = str(evaluate_round)
    else:
        slice_dir = revision_dir / focus
        slice_dir.mkdir(parents=True, exist_ok=True)
        evaluate_round = _allocate_per_l_round(slice_dir)
        # Per-L rounds live on evaluate-state.md; do not bump revision-global.
    save_workflow_state(ws_path, merged, merge=False)

    return {
        "ok": True,
        "current_state": "Working",
        "focus": focus,
        "phase": "evaluating",
        "evaluate_round": evaluate_round,
        "layout": layout,
        "transitioned": True,
    }


def rollback_evaluating_phase(
    revision_dir: Path,
    *,
    focus: str,
) -> None:
    """Undo ``phase=evaluating`` after a failed evaluate-state init (first enter)."""
    tree = load_dependency_tree(revision_dir)
    pointer = load_discussion_pointer(revision_dir)
    cell = pointer["by_id"][focus]
    if cell.get("phase") == "evaluating":
        cell["phase"] = "in_progress"
        save_discussion_pointer(revision_dir, pointer, tree=tree)


def transition_to_evaluating(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Deprecated alias for enter_evaluating_state."""
    return enter_evaluating_state(cycle_id, project_root, profile_id=profile_id)
