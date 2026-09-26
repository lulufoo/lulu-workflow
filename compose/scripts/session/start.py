#!/usr/bin/env python3
"""Staged Compose Start: publish a new revision from holder-provided inputs.

Requires ``--profile-path`` and ``--scope-package``. Does not load holder adapters.
After publish, commits cycle-visible stage pointers and holder_finalized=true.

Design rationale:
docs/archive/lulu-workflow/compose/archive-33.0/compose-outer-shell-management-subdesign.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import uuid
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
from start_gate import check_gate, get_topic_doc  # noqa: E402

from delivered_refs_schema import DeliveredRef, load_delivered_refs_file  # noqa: E402
from execution_state_schema import (  # noqa: E402
    build_execution_state,
    execution_dir,
    load_execution_state,
    save_execution_state,
)
from holder_finalize_control import finalize_holder  # noqa: E402
from resolved_refs_schema import freeze_delivered_copy, write_resolved_refs  # noqa: E402
from revision_lock import LockTimeoutError, session_lock  # noqa: E402
from scope_package_schema import (  # noqa: E402
    build_scope_package,
    load_scope_package,
    save_scope_package,
    validate_scope_package,
)
from session_state_schema import (  # noqa: E402
    load_active_doc,
    load_session_state,
    save_session_state,
)
from workflow_common import CACHE_DIR, detect_cycle_type  # noqa: E402
from workflow_paths import (  # noqa: E402
    read_profile_for_start,
    validate_compose_profile_path,
)
from workflow_profile_paths import (  # noqa: E402
    session_state_path as profile_session_state_path,
    state_path as profile_state_path,
)
from workflow_state_schema import init_compose_session, load_workflow_state  # noqa: E402

_REV_DIR = re.compile(r"^revision(\d+)$")
_STAGING = re.compile(r"^\.staging-revision(\d+)-")


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _failure(code: str, error: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "command": "start",
        "code": code,
        "error": error,
    }
    payload.update(extra)
    return payload


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _revision_numbers(session_dir: Path) -> list[int]:
    nums: list[int] = []
    if not session_dir.is_dir():
        return nums
    for child in session_dir.iterdir():
        match = _REV_DIR.fullmatch(child.name)
        if match and child.is_dir():
            nums.append(int(match.group(1)))
    return nums


def _reserve_revision(session_dir: Path, ss_path: Path) -> int:
    nums = _revision_numbers(session_dir)
    active = 0
    if ss_path.is_file():
        try:
            active = int(load_session_state(ss_path)["active_doc"])
        except ValueError:
            try:
                active = load_active_doc(ss_path)
            except ValueError:
                active = 0
    return 1 + max([active, *nums], default=0)


def _canonicalize_scope_package(package: dict[str, Any]) -> dict[str, Any]:
    """Require an absolute, already-resolved, existing ``source_path``."""
    raw = str(package.get("source_path", "")).strip()
    path = Path(raw)
    if not path.is_absolute():
        raise ValueError("scope-package.source_path must be an absolute path")
    resolved = path.resolve(strict=True)
    if str(resolved) != raw:
        raise ValueError(
            f"scope-package.source_path must equal resolve(strict=True); got {raw!r}"
        )
    built = build_scope_package(
        source_path=raw,
        source_id=package.get("source_id"),
        title=package.get("title"),
    )
    errors = validate_scope_package(built)
    if errors:
        raise ValueError("; ".join(errors))
    return built


def _should_complete_pending_handshake(session_dir: Path, ss_path: Path) -> bool:
    """True when a prior Start published a session but cycle-visible commit did not finish."""
    if not ss_path.is_file():
        return False
    try:
        existing = load_session_state(ss_path)
    except ValueError:
        return False
    if existing["holder_finalized"] is True:
        return False
    ws_path = session_dir / f"revision{existing['active_doc']}" / "workflow-state.md"
    if not ws_path.is_file():
        return True
    try:
        state = load_workflow_state(ws_path)
    except ValueError:
        return True
    return str(state.get("current_state")) != "Invalidated"


def _success_payload(
    *,
    profile_id: str,
    ss_path: Path,
    session_dir: Path,
    topic_doc: Path | None = None,
) -> dict[str, Any]:
    state = load_session_state(ss_path)
    active_doc = int(state["active_doc"])
    final_dir = (session_dir / f"revision{active_doc}").resolve()
    package = load_scope_package(final_dir / "scope-package.json")
    execution = load_execution_state(final_dir)
    payload = {
        "ok": True,
        "command": "start",
        "start_id": str(state["start_id"]),
        "active_doc": active_doc,
        "profile_id": profile_id,
        "profile_path": str(state["profile_path"]),
        "profile_digest": str(state["profile_digest"]),
        "revision_dir": str(final_dir),
        "execution_dir": str(execution_dir(final_dir)),
        "session_state": "Working",
        "execution_state": str(execution["state"]),
        "source_path": str(package["source_path"]),
        "holder_finalized": True,
    }
    if topic_doc is not None:
        payload["topic_doc"] = str(topic_doc)
    return payload


def _cleanup_staging(session_dir: Path) -> None:
    if not session_dir.is_dir():
        return
    for child in session_dir.iterdir():
        if child.is_dir() and _STAGING.match(child.name):
            shutil.rmtree(child, ignore_errors=True)


def _validate_published(revision_dir: Path, digest: str) -> None:
    runtime = revision_dir / "runtime-profile.json"
    if not runtime.is_file():
        raise ValueError("runtime-profile.json missing after publish")
    if _file_digest(runtime) != digest:
        raise ValueError("runtime-profile digest mismatch after publish")
    package = load_scope_package(revision_dir / "scope-package.json")
    _canonicalize_scope_package(package)
    load_execution_state(revision_dir)
    if not execution_dir(revision_dir).is_dir():
        raise ValueError("execution/ missing after publish")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start a new compose revision from holder profile + scope-package.",
    )
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID.")
    parser.add_argument(
        "--profile-path",
        required=True,
        help="Path to holder-provided runtime compose-profile.json.",
    )
    parser.add_argument(
        "--scope-package",
        required=True,
        help="Path to holder-normalized scope-package.json.",
    )
    parser.add_argument(
        "--conversation-id",
        default="",
        help="Optional conversation id recorded on cycle active-context.",
    )
    return parser.parse_args()


def run_start(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    profile_json_path = Path(args.profile_path).expanduser()
    if not profile_json_path.is_absolute():
        profile_json_path = (project_root / profile_json_path).resolve()
    scope_package_path = Path(args.scope_package).expanduser()
    if not scope_package_path.is_absolute():
        scope_package_path = (project_root / scope_package_path).resolve()

    try:
        validate_compose_profile_path(profile_json_path)
        profile = read_profile_for_start(profile_json_path)
    except ValueError as exc:
        return _failure("invalid_profile", str(exc))
    profile_id = str(profile.get("profile_id", "")).strip()
    cache_subdir = str(profile.get("cache_subdir", "")).strip()
    if not cache_subdir:
        return _failure("invalid_profile", "profile missing cache_subdir")

    if not scope_package_path.is_file():
        return _failure("invalid_scope_package", f"scope-package not found: {scope_package_path}")
    try:
        incoming = load_scope_package(scope_package_path)
        package = _canonicalize_scope_package(incoming)
    except (OSError, ValueError) as exc:
        return _failure("invalid_scope_package", str(exc))

    cycle_type = detect_cycle_type(cycle_id)
    cache_dir = project_root / CACHE_DIR
    ss_path = project_root / profile_session_state_path(cycle_id, profile_id, project_root)
    session_dir = ss_path.parent
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        ok, reason = check_gate(cycle_id, profile["stage_name"], cycle_type, cache_dir)
    except Exception as exc:  # noqa: BLE001
        return _failure("gate_blocked", str(exc))
    if not ok:
        return _failure("gate_blocked", str(reason))
    try:
        topic_doc = get_topic_doc(cycle_id, str(profile["stage_name"]), cache_dir)
    except ValueError as exc:
        return _failure("topic_unresolved", str(exc))

    conversation_id = str(getattr(args, "conversation_id", "") or "")
    try:
        with session_lock(session_dir, exclusive=True):
            if not _should_complete_pending_handshake(session_dir, ss_path):
                start_id = uuid.uuid4().hex
                _cleanup_staging(session_dir)
                active_doc = _reserve_revision(session_dir, ss_path)
                final_dir = session_dir / f"revision{active_doc}"
                if final_dir.exists():
                    active_doc = _reserve_revision(session_dir, ss_path)
                    final_dir = session_dir / f"revision{active_doc}"
                staging = session_dir / f".staging-revision{active_doc}-{start_id}"
                if staging.exists():
                    shutil.rmtree(staging)
                staging.mkdir(parents=True, exist_ok=True)
                try:
                    runtime = staging / "runtime-profile.json"
                    runtime.write_bytes(profile_json_path.read_bytes())
                    digest = _file_digest(runtime)
                    save_scope_package(staging, package)
                    save_execution_state(staging, build_execution_state())
                    execution_dir(staging).mkdir(parents=True, exist_ok=True)
                    try:
                        freeze_delivered_copy(
                            staging,
                            load_delivered_refs_file(cycle_id, project_root),
                        )
                    except (OSError, ValueError, FileNotFoundError):
                        freeze_delivered_copy(staging, {"version": 1, "entries": {}})
                    final_scope = (final_dir / "scope-package.json").resolve()
                    write_resolved_refs(
                        staging,
                        cycle_id=cycle_id,
                        stage=profile_id,
                        run_mode="tech",
                        scope_ref=DeliveredRef(
                            type="scope-package",
                            path=str(final_scope),
                            artifact="scope-package",
                        ),
                        intent_baseline_refs=[],
                        norm_constraint_refs=[],
                    )
                    ws_path = staging / "workflow-state.md"
                    init_compose_session(ws_path, mode="tech", cycle_type=cycle_type)
                    _validate_published(staging, digest)
                    staging.rename(final_dir)
                    _validate_published(final_dir, digest)
                except BaseException:
                    if staging.exists():
                        shutil.rmtree(staging, ignore_errors=True)
                    raise
                runtime_final = (final_dir / "runtime-profile.json").resolve()
                save_session_state(
                    ss_path,
                    active_doc=active_doc,
                    profile_path=str(runtime_final),
                    profile_digest=digest,
                    start_id=start_id,
                    holder_finalized=False,
                )
    except LockTimeoutError:
        return _failure("lock_timeout", "session lock timeout")
    except (OSError, ValueError) as exc:
        return _failure("start_failed", str(exc))

    fin = finalize_holder(
        cycle_id=cycle_id,
        project_root=project_root,
        conversation_id=conversation_id,
        profile_id=profile_id,
        confirm=True,
    )
    if not fin.get("ok"):
        if ss_path.is_file():
            try:
                existing = load_session_state(ss_path)
            except ValueError:
                existing = None
            if existing and existing["holder_finalized"] is True:
                return _success_payload(
                    profile_id=profile_id,
                    ss_path=ss_path,
                    session_dir=session_dir,
                    topic_doc=topic_doc,
                )
        return _failure(
            str(fin.get("code") or "start_failed"),
            str(fin.get("error") or "cycle-visible commit failed"),
        )
    return _success_payload(
        profile_id=profile_id,
        ss_path=ss_path,
        session_dir=session_dir,
        topic_doc=topic_doc,
    )


def main() -> int:
    args = parse_args()
    return _emit(run_start(args))


if __name__ == "__main__":
    raise SystemExit(main())
