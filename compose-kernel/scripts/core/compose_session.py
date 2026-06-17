"""Profile-aware compose session path and presentation helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_CORE = Path(__file__).resolve().parent
_SCRIPTS = _CORE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from session_state_schema import load_active_doc  # noqa: E402
from compose_doc_schema import extract_presentation  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, load_profile  # noqa: E402
from workflow_profile_paths import (  # noqa: E402
    approval_path as profile_approval_path,
    document_path,
    session_state_path,
    state_path,
)


def resolve_profile(profile_id: str) -> dict[str, Any]:
    """Load compose profile; ``profile_id`` is the stage name (e.g. tech-plan)."""
    pid = profile_id.strip()
    profile = load_profile(pid)
    if profile.get("profile_id") != pid:
        raise ValueError(
            f"profile_id mismatch: requested {pid!r}, "
            f"got {profile.get('profile_id')!r}",
        )
    return profile


def stage_name(profile_id: str) -> str:
    """Return transition-table stage key for this profile."""
    name = resolve_profile(profile_id).get("stage_name", profile_id)
    if name != profile_id:
        raise ValueError(
            f"stage_name {name!r} != profile {profile_id!r} "
            "(compose kernel expects them to match)",
        )
    return name


def eval_workflow_id(profile_id: str) -> str:
    """Return eval adapter workflow id from profile eval section."""
    eval_cfg = resolve_profile(profile_id).get("eval") or {}
    workflow_id = eval_cfg.get("workflow_id")
    if not workflow_id:
        raise ValueError(f"profile {profile_id!r} has no eval.workflow_id")
    return str(workflow_id)


def load_active_doc_for_profile(
    cycle_id: str,
    project_root: Path,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> int:
    path = project_root / session_state_path(cycle_id, profile_id)
    return load_active_doc(path, default=1)


def workflow_state_path(
    cycle_id: str,
    project_root: Path,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    active_doc = load_active_doc_for_profile(cycle_id, project_root, profile_id)
    return project_root / state_path(cycle_id, active_doc, profile_id)


def document_file_path(
    cycle_id: str,
    project_root: Path,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    active_doc = load_active_doc_for_profile(cycle_id, project_root, profile_id)
    return project_root / document_path(cycle_id, active_doc, profile_id)


def approval_gate_path(
    cycle_id: str,
    project_root: Path,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    active_doc = load_active_doc_for_profile(cycle_id, project_root, profile_id)
    return project_root / profile_approval_path(cycle_id, active_doc, profile_id)


def load_document_presentation(
    cycle_id: str,
    project_root: Path,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    active_doc = load_active_doc_for_profile(cycle_id, project_root, profile_id)
    doc_path = project_root / document_path(cycle_id, active_doc, profile_id)
    payload = extract_presentation(doc_path, revision=active_doc)
    payload["revision"] = active_doc
    return payload


def calibration_note(
    profile_id: str,
    run_mode: str,
    *,
    carry_forward_ref: str = "",
) -> str:
    """Profile-aware post-start guidance for the orchestrator."""
    if profile_id == "tech-design":
        return (
            "设计阶段：Initializing 完成后暂停；可选 Evaluating（d1 代码库一致性 + "
            "d2 方案质量）或 Deliver。"
        )
    if run_mode == "product":
        if carry_forward_ref:
            return (
                "⚠️  carry_forward_ref 存在，进入 Drafting 后必须强制校准"
                "（对比新 product-doc 与旧 tech-doc）。"
            )
        return (
            "首次起草（产品需求模式），进入 Drafting 后必须校准"
            "（读取模板 + 架构约束 + product-doc）。"
        )
    return (
        "技改模式：E1 意图对齐评估将跳过，仅执行 E2（代码库一致性）"
        " + E3（方案质量 / TPEF）。"
    )
