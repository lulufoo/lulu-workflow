#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parent
_SCRIPTS = _CORE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from workflow_paths import WORKFLOW_SCRIPTS  # noqa: E402

sys.path.insert(0, str(WORKFLOW_SCRIPTS))
from cycle_schema import write_stage as write_cycle_state  # noqa: E402
from start_gate import check_gate, get_topic_doc  # noqa: E402
from transition_table import load_stage_order  # noqa: E402
from workflow_sessions import current_effective_delivered, get_sessions  # noqa: E402
from invalidation_hook import invalidate_downstream  # noqa: E402

from delivered_refs_schema import (  # noqa: E402
    load_delivered_refs_file,
    serialize_delivered_refs,
)
from resolved_refs_schema import freeze_delivered_copy, write_resolved_refs  # noqa: E402
from session_state_schema import load_active_doc, next_doc_round, save_active_doc
from start_adapter import StartAdapter, load_start_adapter
from workflow_profile_paths import (
    session_state_path as profile_session_state_path,
    state_path as profile_state_path,
)
from workflow_common import (
    CACHE_DIR,
    detect_cycle_type,
    load_container_meta,
    write_active_context,
)
from workflow_state_schema import init_compose_session, mark_historical

from scope_resolver import resolve_role_summary, ScopeResolverError  # noqa: E402

from workflow_paths import (  # noqa: E402
    read_profile_for_start,
    validate_compose_profile_path,
    write_profile_pointer,
)


def _bump_active_doc(cycle_id: str, project_root: Path, profile_id: str) -> int:
    path = project_root / profile_session_state_path(cycle_id, profile_id, project_root)
    active_doc = next_doc_round(path)
    save_active_doc(path, active_doc)
    return active_doc


def _find_latest_delivered_stage(cycle_id: str, cycle_type: str,
                                  cache_dir: Path) -> "str | None":
    """Return the last stage in cycle order where current_effective_delivered is True."""
    try:
        stages = load_stage_order(cycle_type)
    except Exception:
        return None
    latest = None
    for s in stages:
        if current_effective_delivered(cycle_id, s, cache_dir):
            latest = s
    return latest


def _mark_latest_delivered_historical(cycle_id: str, stage: str, cache_dir: Path) -> None:
    """Mark the current effective delivered session as historical."""
    sessions = [s for s in get_sessions(cycle_id, stage, cache_dir)
                if s.state != "Invalidated"]
    if not sessions:
        return
    latest = max(sessions, key=lambda s: (s.created_at, s.revision))
    if latest.state_path and latest.state_path.exists():
        mark_historical(latest.state_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a new compose workflow session.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID (from cycle_init.py).")
    parser.add_argument(
        "--profile-path",
        required=True,
        help="Path to runtime compose-profile.json (holder-provided).",
    )
    parser.add_argument(
        "--conversation-id",
        default="",
        help="Cursor/Copilot conversation ID for active-context indexing.",
    )
    return parser.parse_known_args()[0]


def _profile_path_from_args(args: argparse.Namespace) -> Path:
    profile_json_path = Path(args.profile_path).expanduser()
    if not profile_json_path.is_absolute():
        profile_json_path = (Path(args.project_root).resolve() / profile_json_path).resolve()
    return profile_json_path


def run_start(
    args: argparse.Namespace,
    adapter: StartAdapter,
) -> int:
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    profile_json_path = Path(args.profile_path).expanduser()
    if not profile_json_path.is_absolute():
        profile_json_path = (project_root / profile_json_path).resolve()
    try:
        validate_compose_profile_path(profile_json_path)
        profile = read_profile_for_start(profile_json_path)
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    profile_id = str(profile.get("profile_id", "")).strip()
    if not profile_id:
        print("错误：compose-profile.json missing profile_id", file=sys.stderr)
        return 1
    cache_subdir = str(profile.get("cache_subdir", "")).strip()
    if not cache_subdir:
        print("错误：profile 缺少 cache_subdir", file=sys.stderr)
        return 1
    to_stage = profile["stage_name"]

    cycle_type = detect_cycle_type(cycle_id)

    cache_dir = project_root / CACHE_DIR

    run_mode = adapter.infer_run_mode(cycle_id, project_root)

    start_errors = adapter.validate_for_start(
        cycle_id,
        project_root,
        run_mode=run_mode,
    )
    if start_errors:
        print("错误：start 校验失败：", file=sys.stderr)
        for err in start_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    delivered_refs = adapter.resolve_delivered_refs(
        cycle_id,
        project_root,
        run_mode=run_mode,
    )
    if not delivered_refs:
        print("错误：delivered_refs 快照为空（start 校验已通过但无可写入条目）", file=sys.stderr)
        return 1

    try:
        load_container_meta(cache_dir, cycle_id, cycle_type)
    except ValueError as e:
        print(f"错误：{e}")
        return 1

    if current_effective_delivered(cycle_id, to_stage, cache_dir):
        _mark_latest_delivered_historical(cycle_id, to_stage, cache_dir)
        invalidate_downstream(cycle_id, to_stage, cycle_type, cache_dir)

    latest_stage = _find_latest_delivered_stage(cycle_id, cycle_type, cache_dir)
    if latest_stage:
        try:
            _stages = load_stage_order(cycle_type)
        except Exception:
            _stages = []
        if to_stage in _stages and latest_stage in _stages:
            if _stages.index(to_stage) < _stages.index(latest_stage):
                invalidate_downstream(cycle_id, to_stage, cycle_type, cache_dir)

    ok, reason = check_gate(cycle_id, to_stage, cycle_type, cache_dir)
    if not ok:
        print(f"Gate blocked: {reason}", file=sys.stderr)
        sys.exit(1)

    write_profile_pointer(project_root, cycle_id, cache_subdir, profile_json_path)

    try:
        topic_doc = get_topic_doc(cycle_id, to_stage, cache_dir)
        if topic_doc:
            print(f"Topic doc: {topic_doc}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    active_doc = _bump_active_doc(cycle_id, project_root, profile_id)
    ss_path = project_root / profile_session_state_path(cycle_id, profile_id, project_root)
    write_active_context(
        project_root,
        cycle_id,
        conversation_id=args.conversation_id.strip() or None,
        stage=to_stage,
        cycle_type=cycle_type,
    )
    write_cycle_state(cycle_id, to_stage, cache_dir)

    ws_path = project_root / profile_state_path(cycle_id, active_doc, profile_id, project_root)
    init_compose_session(
        ws_path,
        mode=run_mode,
        cycle_type=cycle_type,
    )

    # Per-revision provenance artifacts (see resolved_refs_schema):
    #   ① frozen full copy of the mutable cycle delivered-refs.json (audit baseline)
    #   ② stage-resolved three refs — compose consumers read this
    # Scope resolution runs after revision_dir exists so design can write
    # scope-package.json once under the new revision (archive-1.0 P3 D3).
    revision_dir = ws_path.parent
    try:
        scope_refs = adapter.resolve_scope_refs(
            delivered_refs=delivered_refs,
            run_mode=run_mode,
            revision_dir=revision_dir,
        )
    except ValueError as e:
        print(f"错误：scope_refs 解析失败：{e}", file=sys.stderr)
        return 1
    if not scope_refs:
        print("错误：scope_refs 快照为空（无法解析 primary scope SSOT）", file=sys.stderr)
        return 1

    intent_baseline_refs = adapter.resolve_intent_baseline_refs(
        delivered_refs=delivered_refs,
        run_mode=run_mode,
    )
    norm_constraint_refs = adapter.resolve_norm_constraint_refs(
        cycle_id=cycle_id,
        project_root=project_root,
        delivered_refs=delivered_refs,
    )
    freeze_delivered_copy(revision_dir, load_delivered_refs_file(cycle_id, project_root))
    write_resolved_refs(
        revision_dir,
        cycle_id=cycle_id,
        stage=profile_id,
        run_mode=run_mode,
        scope_ref=scope_refs[0],
        intent_baseline_refs=intent_baseline_refs,
        norm_constraint_refs=norm_constraint_refs,
    )

    # P4.convert (C1=A): when $SCOPE_REF is scope-package.json, hard-convert once.
    from scope_package_convert import (  # noqa: WPS433
        ScopePackageConvertError,
        ensure_scope_package_convert,
    )
    from scope_package_schema import is_scope_package_path  # noqa: WPS433

    scope_path = Path(scope_refs[0].path)
    if is_scope_package_path(scope_path):
        try:
            ensure_scope_package_convert(
                revision_dir,
                scope_package_path=scope_path,
            )
        except ScopePackageConvertError as exc:
            print(f"错误：scope-package convert 失败：{exc}", file=sys.stderr)
            return 1

    try:
        role_summary = resolve_role_summary(cycle_type=cycle_type)
    except ScopeResolverError:
        role_summary = cycle_type

    note = adapter.post_start_guidance(
        run_mode=run_mode,
        scope_refs=scope_refs,
    )

    doc_label = profile["document"]["filename"]
    refs_json = serialize_delivered_refs(delivered_refs)
    scope_json = serialize_delivered_refs(scope_refs)
    inductive = (profile.get("pipeline") or {}).get("inductive")
    print(f"""
会话已启动。

会话状态文件：{ss_path.as_posix()}
当前文档：    revision{active_doc} / {doc_label}
状态文件：    {ws_path.as_posix()}
当前状态：    Split
运行模式：    {run_mode}
Profile：     {profile_id}
pipeline.inductive: {json.dumps(bool(inductive))}
Cycle type：  {role_summary}
评估轮次：    0
delivered_refs：{refs_json}
scope（派生）：{scope_json}

{note}
""")
    return 0


def main() -> int:
    args = parse_args()
    profile_json_path = _profile_path_from_args(args)
    try:
        validate_compose_profile_path(profile_json_path)
        profile = read_profile_for_start(profile_json_path)
        adapter = load_start_adapter(profile, profile_json_path)
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return run_start(args, adapter)


if __name__ == "__main__":
    raise SystemExit(main())
