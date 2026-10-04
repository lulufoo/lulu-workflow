#!/usr/bin/env python3
"""Dispatch inputs printed by ``$EXECUTION enter-*`` for the runner skills."""

from __future__ import annotations

import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_session import document_file_path  # noqa: E402
from delivered_refs_schema import serialize_delivered_refs  # noqa: E402
from execution_state_schema import execution_dir  # noqa: E402
from resolved_refs_schema import (  # noqa: E402
    intent_baseline_from_workflow,
    norm_constraint_from_workflow,
    primary_scope_from_workflow,
    resolved_scope_ref,
)
from scope_package_schema import (  # noqa: E402
    is_scope_package_path,
    load_scope_package,
    scope_package_path,
    scope_source_path,
)
from workflow_common import detect_cycle_type  # noqa: E402
from workflow_paths import load_profile  # noqa: E402


def pipeline_config(cycle_id: str, project_root: Path, profile_id: str) -> dict:
    profile = load_profile(profile_id, project_root=project_root, cycle_id=cycle_id)
    return profile.get("pipeline") or {}


def scope_doc(revision_dir: Path, cycle_id: str, project_root: Path, profile_id: str) -> Path:
    """The ``$SCOPE_REF`` document: scope-package.json of this revision when present."""
    packaged = scope_package_path(revision_dir)
    if packaged.is_file():
        return packaged
    ref = resolved_scope_ref(revision_dir)
    if ref is not None and str(ref.path).strip():
        path = Path(ref.path)
        if path.is_file():
            return path
    init_ref = primary_scope_from_workflow(cycle_id, project_root, profile_id)
    if init_ref is None:
        raise ValueError("no scope ref available")
    path = Path(init_ref.path).resolve()
    if not path.is_file():
        raise ValueError(f"scope doc not found: {path}")
    return path


def source_path(scope_path: Path, *, project_root: Path) -> Path:
    """Seed source document: the scope-package ``source_path`` or the scope doc itself."""
    if is_scope_package_path(scope_path):
        return scope_source_path(load_scope_package(scope_path), project_root=project_root)
    return Path(scope_path)


def format_fact_intake_dispatch(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
    *,
    inductive: bool,
    revision_dir: Path,
) -> str:
    scope_path = scope_doc(revision_dir, cycle_id, project_root, profile_id)
    source = source_path(scope_path, project_root=project_root).as_posix()
    return "\n".join(
        [
            f"REVISION_DIR:         {revision_dir.as_posix()}",
            f"EXECUTION_DIR:        {execution_dir(revision_dir).as_posix()}",
            f"CYCLE_ID:             {cycle_id}",
            f"SOURCE_PATH:          {source}",
            f"REQUIRE_SEED_ORIGIN:  {str(inductive).lower()}",
        ]
    )


def format_producer_dispatch(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
    *,
    inductive: bool,
    revision_dir: Path,
) -> str:
    scope_path = scope_doc(revision_dir, cycle_id, project_root, profile_id)
    intent_refs = intent_baseline_from_workflow(cycle_id, project_root, profile_id)
    norm_refs = norm_constraint_from_workflow(cycle_id, project_root, profile_id)
    source = source_path(scope_path, project_root=project_root).as_posix()
    out_dir = execution_dir(revision_dir).as_posix()
    if inductive:
        lines = [
            f"CYCLE_ID:             {cycle_id}",
            f"SCOPE_REF:            {source}",
            f"SOURCE_PATH:          {source}",
            f"INTENT_BASELINE_REFS: {serialize_delivered_refs(intent_refs)}",
            f"NORM_CONSTRAINT_REFS: {serialize_delivered_refs(norm_refs)}",
            f"INDUCTIVE_OUT_DIR:    {out_dir}",
        ]
        return "\n".join(lines)
    pipeline = pipeline_config(cycle_id, project_root, profile_id)
    lines = [
        f"CYCLE_ID:             {cycle_id}",
        f"SCOPE_REF:            {scope_path.as_posix()}",
        f"INTENT_BASELINE_REFS: {serialize_delivered_refs(intent_refs)}",
        f"NORM_CONSTRAINT_REFS: {serialize_delivered_refs(norm_refs)}",
        f"DEDUCTIVE_OUT_DIR:    {revision_dir.as_posix()}",
        f"CODE_GROUNDING:       {str(bool(pipeline.get('code_grounding'))).lower()}",
        f"SOURCE_PATH:          {source}",
    ]
    return "\n".join(lines)


def format_writing_dispatch(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
    revision_dir: Path,
) -> str:
    output_doc = document_file_path(cycle_id, project_root, profile_id)
    code_grounding = bool(pipeline_config(cycle_id, project_root, profile_id).get("code_grounding"))
    scope_path = scope_doc(revision_dir, cycle_id, project_root, profile_id)
    return "\n".join(
        [
            f"REVISION_DIR:         {revision_dir.as_posix()}",
            f"SCOPE_REF_PATH:       {scope_path.as_posix()}",
            f"OUTPUT_DOC_PATH:      {output_doc.resolve().as_posix()}",
            f"CYCLE_TYPE:           {detect_cycle_type(cycle_id)}",
            f"CYCLE_ID:             {cycle_id}",
            f"CODE_GROUNDING:       {str(code_grounding).lower()}",
        ]
    )


def derive_step_next_actions(
    state: str,
    *,
    writing_ok: bool,
    freeedit: bool,
    fact_intake_ok: bool = False,
    inductive: bool = False,
    inductive_ok: bool = False,
    deductive_ok: bool = False,
) -> list[str]:
    if state == "Pending":
        return ["enter-fact-intake"]
    if state == "FactIntake":
        if not fact_intake_ok:
            return ["run-fact-intake"]
        return ["enter-inductive"] if inductive else ["enter-deductive"]
    if state == "Inductive":
        return ["enter-deductive"] if inductive_ok else ["run-inductive"]
    if state == "Deductive":
        return ["enter-writing"] if deductive_ok else ["run-deductive"]
    if state == "Writing":
        if not writing_ok:
            return ["run-writing"]
        return ["enter-freeedit", "begin-eval-round"] if freeedit else ["begin-eval-round"]
    if state == "FreeEdit":
        actions = ["begin-eval-round"]
        if inductive:
            actions.append("reverse-to-inductive")
        actions.extend(["reverse-to-deductive", "reverse-to-writing"])
        return actions
    if state == "Evaluating":
        return ["accept", "fix", "re-evaluate"]
    return []
