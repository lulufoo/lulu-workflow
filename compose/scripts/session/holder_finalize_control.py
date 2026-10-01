#!/usr/bin/env python3
"""Holder finalize handshake after Compose Start.

Called by start after a revision is published, or when retrying an
unfinished publish. Commits cycle-visible side effects and sets
holder_finalized=true. Not a SKILL step.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_CORE = Path(__file__).resolve().parent
_SCRIPTS = _CORE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from workflow_paths import WORKFLOW_SCRIPTS  # noqa: E402

sys.path.insert(0, str(WORKFLOW_SCRIPTS))
from cycle_schema import write_stage as write_cycle_state  # noqa: E402
from cycle_delivered_refs import remove_delivered_ref  # noqa: E402
from invalidation_hook import invalidate_downstream_under_cycle_lock  # noqa: E402
from transition_table import load_stage_order  # noqa: E402
from workflow_sessions import current_effective_delivered, get_sessions  # noqa: E402

from revision_lock import LockTimeoutError, cycle_lock, revision_lock, session_lock  # noqa: E402
from session_state_schema import load_session_state, save_session_state  # noqa: E402
from workflow_common import CACHE_DIR, detect_cycle_type, write_active_context  # noqa: E402
from workflow_paths import load_profile_json, write_active_profile  # noqa: E402
from workflow_profile_paths import session_state_path  # noqa: E402
from workflow_state_schema import load_workflow_state, mark_historical  # noqa: E402


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _failure(code: str, error: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "command": "holder-finalize",
        "code": code,
        "error": error,
    }
    payload.update(extra)
    return payload


def _delivered_sessions(cycle_id: str, stage: str, cache_dir: Path) -> list:
    return [
        item
        for item in get_sessions(cycle_id, stage, cache_dir)
        if item.state == "Delivered"
    ]


def _mark_latest_delivered_historical(cycle_id: str, stage: str, cache_dir: Path) -> None:
    sessions = _delivered_sessions(cycle_id, stage, cache_dir)
    if not sessions:
        return
    latest = max(sessions, key=lambda item: (item.created_at, item.revision))
    if latest.state_path and latest.state_path.exists():
        mark_historical(latest.state_path)


def _profile_id_from_state(root: Path, state: dict[str, Any]) -> str:
    raw = Path(str(state["profile_path"]))
    profile_file = raw if raw.is_absolute() else (root / raw)
    try:
        profile = load_profile_json(profile_file)
    except (OSError, ValueError) as exc:
        raise ValueError(f"runtime profile unreadable: {exc}") from exc
    profile_id = str(profile.get("profile_id", "")).strip()
    if not profile_id:
        raise ValueError("runtime profile missing profile_id")
    return profile_id


def _resolve_finalize_target(
    root: Path,
    cycle_id: str,
    profile_id: str | None = None,
) -> tuple[Path, str]:
    if profile_id:
        ss_path = (root / session_state_path(cycle_id, profile_id, root)).resolve()
        state = load_session_state(ss_path)
        resolved = _profile_id_from_state(root, state)
        if resolved != profile_id:
            raise ValueError(
                f"runtime profile_id {resolved!r} != {profile_id!r}"
            )
        return ss_path, resolved
    cache = root / CACHE_DIR / cycle_id
    if not cache.is_dir():
        raise ValueError("no compose session cache for cycle")
    pending: list[Path] = []
    for path in cache.rglob("session-state.md"):
        try:
            state = load_session_state(path)
        except ValueError:
            continue
        if state["holder_finalized"] is False:
            pending.append(path)
    if not pending:
        raise ValueError("no pending holder finalize")
    if len(pending) > 1:
        raise ValueError("ambiguous pending holder finalize")
    ss_path = pending[0]
    return ss_path, _profile_id_from_state(root, load_session_state(ss_path))


def finalize_holder(
    *,
    cycle_id: str,
    project_root: Path,
    conversation_id: str = "",
    profile_id: str = "",
    confirm: bool,
) -> dict[str, Any]:
    if not confirm:
        return _failure(
            "confirmation_required",
            "holder-finalize requires --confirm",
        )
    root = project_root.resolve()
    cache_dir = root / CACHE_DIR
    cycle_cache = cache_dir / cycle_id
    cycle_type = detect_cycle_type(cycle_id)

    try:
        with cycle_lock(cycle_cache, exclusive=True):
            try:
                ss_path, profile_id = _resolve_finalize_target(
                    root,
                    cycle_id,
                    profile_id.strip() or None,
                )
            except ValueError as exc:
                return _failure("stale_holder_finalize", str(exc))
            session_dir = ss_path.parent
            with session_lock(session_dir, exclusive=True):
                try:
                    state = load_session_state(ss_path)
                except ValueError as exc:
                    return _failure("stale_holder_finalize", str(exc))
                if state["holder_finalized"] is True:
                    return {
                        "ok": True,
                        "command": "holder-finalize",
                        "holder_finalized": True,
                        "transitioned": False,
                        "active_doc": int(state["active_doc"]),
                        "start_id": str(state["start_id"]),
                    }
                revision_dir = (
                    session_dir / f"revision{int(state['active_doc'])}"
                ).resolve()
                with revision_lock(revision_dir, exclusive=False):
                    ws_path = revision_dir / "workflow-state.md"
                    try:
                        workflow = load_workflow_state(ws_path)
                    except ValueError as exc:
                        return _failure("stale_holder_finalize", str(exc))
                    current = str(workflow.get("current_state"))
                    if current == "Invalidated":
                        return _failure(
                            "stale_holder_finalize",
                            "revision is Invalidated",
                        )
                    if current != "Working":
                        return _failure(
                            "finalize_invalid_state",
                            f"workflow-state is {current!r}, expected Working",
                        )
                    snapshot = dict(state)
            remove_delivered_ref(cycle_id, root, profile_id)
            prior_delivered = bool(
                _delivered_sessions(cycle_id, profile_id, cache_dir)
            )
            if prior_delivered:
                _mark_latest_delivered_historical(cycle_id, profile_id, cache_dir)
            try:
                stages = load_stage_order(cycle_type)
            except Exception:
                stages = []
            latest_stage = None
            for stage in stages:
                if current_effective_delivered(cycle_id, stage, cache_dir):
                    latest_stage = stage
            backfill = bool(
                latest_stage
                and profile_id in stages
                and latest_stage in stages
                and stages.index(profile_id) < stages.index(latest_stage)
            )
            if prior_delivered or backfill:
                invalidate_downstream_under_cycle_lock(
                    cycle_id,
                    profile_id,
                    cycle_type,
                    cache_dir,
                    project_root=root,
                )
            write_active_profile(root, cycle_id, profile_id)
            write_cycle_state(cycle_id, profile_id, cache_dir)
            write_active_context(
                root,
                cycle_id,
                conversation_id=conversation_id.strip() or None,
                stage=profile_id,
                cycle_type=cycle_type,
            )
            with session_lock(session_dir, exclusive=True):
                with revision_lock(revision_dir, exclusive=True):
                    try:
                        state = load_session_state(ss_path)
                        workflow = load_workflow_state(ws_path)
                    except ValueError as exc:
                        return _failure("stale_holder_finalize", str(exc))
                    if (
                        str(state["start_id"]) != str(snapshot["start_id"])
                        or int(state["active_doc"]) != int(snapshot["active_doc"])
                        or str(state["profile_digest"]) != str(snapshot["profile_digest"])
                    ):
                        return _failure(
                            "stale_holder_finalize",
                            "identity changed before finalize commit",
                        )
                    if str(workflow.get("current_state")) != "Working":
                        return _failure(
                            "finalize_invalid_state",
                            "workflow-state is no longer Working",
                        )
                    save_session_state(
                        ss_path,
                        active_doc=int(snapshot["active_doc"]),
                        profile_path=str(snapshot["profile_path"]),
                        profile_digest=str(snapshot["profile_digest"]),
                        start_id=str(snapshot["start_id"]),
                        holder_finalized=True,
                    )
    except LockTimeoutError:
        return _failure("lock_timeout", "lock timeout")
    except (OSError, ValueError) as exc:
        return _failure("finalize_failed", str(exc))

    return {
        "ok": True,
        "command": "holder-finalize",
        "holder_finalized": True,
        "transitioned": True,
        "active_doc": int(snapshot["active_doc"]),
        "start_id": str(snapshot["start_id"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finalize holder handshake after Compose Start")
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--conversation-id", default="")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    return _emit(
        finalize_holder(
            cycle_id=args.cycle_id.strip(),
            project_root=args.project_root.resolve(),
            conversation_id=args.conversation_id,
            confirm=args.confirm,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
