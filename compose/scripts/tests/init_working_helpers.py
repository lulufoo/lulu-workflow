"""Shared helpers for start / draft integration tests."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from delivered_refs_schema import DeliveredRef, load_delivered_refs_file, record_delivered_ref
from execution_checks import EVAL_RUN_FILE, WRITING_STAMP, write_stamp
from execution_state_schema import (
    build_execution_state,
    execution_dir,
    execution_fingerprint,
    execution_state_path,
    save_execution_state,
)
from resolved_refs_schema import freeze_delivered_copy, write_resolved_refs
from scope_package_schema import build_scope_package, save_scope_package
from start_scope_helpers import first_ref
from session_state_schema import load_active_doc, resolve_path
from workflow_common import CACHE_DIR
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, seed_profile_pointer_for_tests
from workflow_profile_paths import state_path
from workflow_state_schema import init_compose_session, save_workflow_state


def seed_execution_revision(revision_dir: Path, *, state: str = "Pending") -> Path:
    """Publish scope-package + execution-state and return ``execution/``."""
    rev = Path(revision_dir).resolve()
    src = rev / "_scope-src.md"
    if not src.is_file():
        src.write_text("# scope\n", encoding="utf-8")
    save_scope_package(rev, build_scope_package(source_path=str(src.resolve())))
    save_execution_state(rev, build_execution_state(state))
    path = execution_dir(rev)
    path.mkdir(parents=True, exist_ok=True)
    return path


def seed_l1_revision(revision_dir: Path) -> None:
    """Compatibility name: seed a single-execution revision."""
    seed_execution_revision(revision_dir)


def ensure_l1_revision(revision_dir: Path, *, producer: str = "Inductive") -> Path:
    """Idempotent: seed execution if missing; return the execution dir."""
    rev = Path(revision_dir).resolve()
    if not execution_state_path(rev).is_file():
        seed_execution_revision(rev, state=producer)
    path = execution_dir(rev)
    path.mkdir(parents=True, exist_ok=True)
    return path


def l1_dir(revision_dir: Path) -> Path:
    """Execution directory for a seeded revision."""
    path = execution_dir(Path(revision_dir).resolve())
    path.mkdir(parents=True, exist_ok=True)
    return path


def mark_focus_producer(revision_dir: Path, state: str = "Inductive") -> None:
    """Set the execution step to Inductive or Deductive (facts write)."""
    if state not in {"Inductive", "Deductive"}:
        raise ValueError(f"producer state must be Inductive or Deductive, got {state!r}")
    save_execution_state(Path(revision_dir).resolve(), build_execution_state(state))


def lock_single_l1_tree(revision_dir: Path) -> None:
    """Compatibility name: seed a single-execution revision."""
    seed_execution_revision(revision_dir)


def init_working_ready(
    path: Path,
    *,
    mode: str,
    cycle_type: str = "feature",
    evaluate_round: int = 0,
) -> None:
    """Init session at Working and publish the execution dir."""
    init_compose_session(
        path,
        mode=mode,
        cycle_type=cycle_type,
        evaluate_round=evaluate_round,
    )
    seed_execution_revision(path.parent)


def mark_all_l_accepted(revision_dir: Path) -> None:
    """Mark execution Completed."""
    save_execution_state(Path(revision_dir).resolve(), build_execution_state("Completed"))


def mark_focus_intake_done(revision_dir: Path) -> None:
    """Execution: Writing (ready for enter-evaluating)."""
    rev = Path(revision_dir).resolve()
    save_execution_state(rev, build_execution_state("Writing"))
    write_stamp(execution_dir(rev), WRITING_STAMP)


def mark_focus_evaluating(revision_dir: Path) -> None:
    """Execution: Evaluating with an active eval_run_id."""
    rev = Path(revision_dir).resolve()
    state = build_execution_state("Evaluating")
    save_execution_state(rev, state)
    ex = execution_dir(rev)
    ex.mkdir(parents=True, exist_ok=True)
    payload = {
        "eval_run_id": uuid.uuid4().hex,
        "execution_fingerprint": execution_fingerprint(state),
    }
    (ex / EVAL_RUN_FILE).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def seed_frozen_delivered(ws_path: Path, refs: list[DeliveredRef]) -> None:
    """Write delivered-refs.json into the revision dir from an explicit ref list."""
    entries = {
        r.type: {
            "delivered_type": r.type,
            "path": r.path,
            "revision": 1,
            "profile_id": r.type,
            "delivered_at": "",
            "source_workflow_state": "",
        }
        for r in refs
    }
    freeze_delivered_copy(ws_path.parent, {"version": 1, "entries": entries})


def seed_resolved_refs_for_eval(
    ws_path: Path,
    *,
    cycle_id: str,
    stage: str,
    mode: str = "tech",
    intent_baseline_refs: list[DeliveredRef] | None = None,
    norm_constraint_refs: list[DeliveredRef] | None = None,
    scope_path: Path | None = None,
) -> Path:
    """Write resolved-refs.json with a readable parent document for Common Eval."""
    revision_dir = ws_path.parent
    src = Path(scope_path) if scope_path is not None else revision_dir / "_scope-src.md"
    if not src.is_file():
        src.write_text("# scope\n", encoding="utf-8")
    write_resolved_refs(
        revision_dir,
        cycle_id=cycle_id,
        stage=stage,
        run_mode=mode,
        scope_ref=DeliveredRef(type="scope", path=str(src.resolve())),
        intent_baseline_refs=intent_baseline_refs or [],
        norm_constraint_refs=norm_constraint_refs or [],
    )
    return src


def seed_provenance_artifacts(
    ws_path: Path,
    *,
    cycle_id: str,
    project_root: Path,
    stage: str,
    mode: str,
    scope_refs: list[DeliveredRef],
    intent_baseline_refs: list[DeliveredRef] | None = None,
    norm_constraint_refs: list[DeliveredRef] | None = None,
) -> None:
    """Mirror start.py: freeze delivered-refs and materialize resolved-refs."""
    revision_dir = ws_path.parent
    freeze_delivered_copy(revision_dir, load_delivered_refs_file(cycle_id, project_root))
    write_resolved_refs(
        revision_dir,
        cycle_id=cycle_id,
        stage=stage,
        run_mode=mode,
        scope_ref=scope_refs[0] if scope_refs else None,
        intent_baseline_refs=intent_baseline_refs or [],
        norm_constraint_refs=norm_constraint_refs or [],
    )


def product_delivered_refs(product_path: str = "/p.md") -> list[DeliveredRef]:
    return [DeliveredRef(type="lulu-spec", path=product_path)]


def tech_diagnostic_refs(decision_path: Path | str) -> list[DeliveredRef]:
    return [DeliveredRef(type="lulu-approach", path=str(Path(decision_path).resolve()))]


def tech_plan_scope_refs(delivered_refs: list[DeliveredRef]) -> list[DeliveredRef]:
    primary = first_ref(delivered_refs, "lulu-design") or first_ref(
        delivered_refs,
        "lulu-approach",
    )
    return [primary] if primary is not None else []


def tech_design_scope_refs(delivered_refs: list[DeliveredRef]) -> list[DeliveredRef]:
    primary = first_ref(delivered_refs, "lulu-approach")
    return [primary] if primary is not None else []


def product_spec_scope_refs(delivered_refs: list[DeliveredRef]) -> list[DeliveredRef]:
    primary = first_ref(delivered_refs, "lulu-bet")
    return [primary] if primary is not None else []


def seed_delivered_refs_file(
    project_root: Path,
    cycle_id: str,
    refs: list[DeliveredRef],
) -> None:
    """Write delivered-refs.json entries for integration tests."""
    for ref in refs:
        record_delivered_ref(
            cycle_id,
            project_root,
            delivered_type=ref.type,
            path=ref.path,
            revision=1,
            profile_id=ref.type,
            source_workflow_state="",
        )


def seed_tech_plan_session(
    project_root: Path,
    *,
    cycle_id: str,
    mode: str = "tech",
    delivered_refs: list[DeliveredRef] | None = None,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    """Seed minimal compose session-state + workflow-state for shell tests."""
    cache_dir = project_root / CACHE_DIR
    diag_dir = cache_dir / cycle_id / "lulu-approach"
    diag_dir.mkdir(parents=True, exist_ok=True)
    decision = diag_dir / "decision-doc.md"
    decision.write_text("# Decision\n", encoding="utf-8")
    refs = delivered_refs
    if refs is None:
        refs = [DeliveredRef(type="lulu-approach", path=str(decision.resolve()))]
    seed_delivered_refs_file(project_root, cycle_id, refs)
    seed_profile_pointer_for_tests(project_root, cycle_id, profile_id)
    active_doc = load_active_doc(resolve_path(cycle_id, project_root, profile_id))
    ws_path = project_root / state_path(cycle_id, active_doc, profile_id, project_root)
    init_working_ready(ws_path, mode=mode)
    seed_provenance_artifacts(
        ws_path,
        cycle_id=cycle_id,
        project_root=project_root,
        stage=profile_id,
        mode=mode,
        scope_refs=tech_plan_scope_refs(refs),
    )
    return ws_path


def seed_tech_design_session(
    project_root: Path,
    *,
    cycle_id: str,
    mode: str = "tech",
    delivered_refs: list[DeliveredRef] | None = None,
) -> Path:
    """Seed lulu-design session with lulu-approach decision-doc scope."""
    cache_dir = project_root / CACHE_DIR
    diag_dir = cache_dir / cycle_id / "lulu-approach"
    diag_dir.mkdir(parents=True, exist_ok=True)
    decision = diag_dir / "decision-doc.md"
    decision.write_text("# Decision\n", encoding="utf-8")
    refs = delivered_refs
    if refs is None:
        refs = [DeliveredRef(type="lulu-approach", path=str(decision.resolve()))]
    seed_delivered_refs_file(project_root, cycle_id, refs)
    seed_profile_pointer_for_tests(project_root, cycle_id, "lulu-design")
    active_doc = load_active_doc(resolve_path(cycle_id, project_root, "lulu-design"))
    ws_path = project_root / state_path(cycle_id, active_doc, "lulu-design", project_root)
    init_working_ready(ws_path, mode=mode)
    intent_refs = []
    if mode == "product":
        spec = first_ref(refs, "lulu-spec")
        if spec is not None:
            intent_refs = [spec]
    seed_provenance_artifacts(
        ws_path,
        cycle_id=cycle_id,
        project_root=project_root,
        stage="lulu-design",
        mode=mode,
        scope_refs=tech_design_scope_refs(refs),
        intent_baseline_refs=intent_refs,
    )
    return ws_path


def seed_product_spec_session(
    project_root: Path,
    *,
    cycle_id: str,
    delivered_refs: list[DeliveredRef] | None = None,
) -> Path:
    """Seed lulu-spec session with lulu-bet decision-doc scope."""
    cache_dir = project_root / CACHE_DIR
    diag_dir = cache_dir / cycle_id / "lulu-bet"
    diag_dir.mkdir(parents=True, exist_ok=True)
    decision = diag_dir / "decision-doc.md"
    decision.write_text("# Decision\n", encoding="utf-8")
    refs = delivered_refs
    if refs is None:
        refs = [DeliveredRef(type="lulu-bet", path=str(decision.resolve()))]
    seed_delivered_refs_file(project_root, cycle_id, refs)
    seed_profile_pointer_for_tests(project_root, cycle_id, "lulu-spec")
    active_doc = load_active_doc(resolve_path(cycle_id, project_root, "lulu-spec"))
    ws_path = project_root / state_path(cycle_id, active_doc, "lulu-spec", project_root)
    init_working_ready(ws_path, mode="product")
    seed_provenance_artifacts(
        ws_path,
        cycle_id=cycle_id,
        project_root=project_root,
        stage="lulu-spec",
        mode="product",
        scope_refs=product_spec_scope_refs(refs),
    )
    return ws_path
