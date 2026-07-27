"""Shared helpers for start / draft integration tests."""

from __future__ import annotations

import json
from pathlib import Path

from delivered_refs_schema import DeliveredRef, load_delivered_refs_file, record_delivered_ref
from multi_slice_control import cmd_lock_tree
from resolved_refs_schema import freeze_delivered_copy, write_resolved_refs
from start_scope_helpers import first_ref
from session_state_schema import bump_active_doc
from workflow_common import CACHE_DIR
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, seed_profile_pointer_for_tests
from workflow_profile_paths import state_path
from workflow_state_schema import init_drafting, save_workflow_state


def lock_single_l1_tree(revision_dir: Path) -> None:
    """Lock an explicit single-node L1 dependency tree (Split complete precondition)."""
    tree = {
        "version": 1,
        "nodes": [{"id": "L1", "title": "Only", "summary": "single"}],
        "edges": [],
        "order": ["L1"],
    }
    rc = cmd_lock_tree(
        Path(revision_dir).resolve(),
        tree_json=json.dumps(tree),
        tree_file=None,
        rulers_json=None,
        rulers_file=None,
        confirm=True,
    )
    if rc != 0:
        raise RuntimeError(f"lock_single_l1_tree failed rc={rc}")


def init_drafting_ready(
    path: Path,
    *,
    mode: str,
    cycle_type: str = "feature",
    carry_forward_ref: str = "",
    evaluate_round: int = 0,
) -> None:
    """Init session at Split, lock L1, advance to Drafting (tests that need Drafting)."""
    init_drafting(
        path,
        mode=mode,
        cycle_type=cycle_type,
        carry_forward_ref=carry_forward_ref,
        evaluate_round=evaluate_round,
    )
    lock_single_l1_tree(path.parent)
    save_workflow_state(path, {"current_state": "Drafting"})


def seed_frozen_delivered(ws_path: Path, refs: list[DeliveredRef]) -> None:
    """Write ① delivered-refs.json into the revision dir from an explicit ref list."""
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
    """Mirror start.py: freeze ① and materialize ② into the revision dir."""
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
    active_doc = bump_active_doc(cycle_id, project_root, profile_id)
    ws_path = project_root / state_path(cycle_id, active_doc, profile_id, project_root)
    init_drafting_ready(ws_path, mode=mode)
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
    active_doc = bump_active_doc(cycle_id, project_root, "lulu-design")
    ws_path = project_root / state_path(cycle_id, active_doc, "lulu-design", project_root)
    init_drafting_ready(ws_path, mode=mode)
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
    active_doc = bump_active_doc(cycle_id, project_root, "lulu-spec")
    ws_path = project_root / state_path(cycle_id, active_doc, "lulu-spec", project_root)
    init_drafting_ready(ws_path, mode="product")
    seed_provenance_artifacts(
        ws_path,
        cycle_id=cycle_id,
        project_root=project_root,
        stage="lulu-spec",
        mode="product",
        scope_refs=product_spec_scope_refs(refs),
    )
    return ws_path
