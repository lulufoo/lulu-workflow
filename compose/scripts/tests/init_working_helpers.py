"""Shared helpers for start / draft integration tests."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from delivered_refs_schema import DeliveredRef, load_delivered_refs_file, record_delivered_ref
from l_ledger_schema import build_ledger, ledger_fingerprint, load_l_ledger, save_l_ledger
from resolved_refs_schema import freeze_delivered_copy, write_resolved_refs
from scope_package_schema import build_scope_package, save_scope_package, write_source_path_mirrors
from start_scope_helpers import first_ref
from session_state_schema import load_active_doc, resolve_path
from workflow_common import CACHE_DIR
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, seed_profile_pointer_for_tests
from workflow_profile_paths import state_path
from workflow_state_schema import init_compose_session, save_workflow_state


def seed_l1_revision(revision_dir: Path) -> None:
    """Publish a single-L ledger, scope-package, and L1 dir."""
    rev = Path(revision_dir).resolve()
    src = rev / "_scope-src.md"
    if not src.is_file():
        src.write_text("# scope\n", encoding="utf-8")
    save_l_ledger(rev, build_ledger(["L1"]))
    package = build_scope_package(
        [{"id": "L1", "title": "Only", "source_path": str(src.resolve())}]
    )
    save_scope_package(rev, package)
    write_source_path_mirrors(rev, package)
    (rev / "L1").mkdir(parents=True, exist_ok=True)


def ensure_l1_revision(revision_dir: Path, *, producer: str = "Inductive") -> Path:
    """Idempotent: seed a single-L ledger if missing; return the L1 dir."""
    rev = Path(revision_dir).resolve()
    from l_ledger_schema import l_ledger_path  # noqa: WPS433

    if not l_ledger_path(rev).is_file():
        seed_l1_revision(rev)
        mark_focus_producer(rev, producer)
    path = rev / "L1"
    path.mkdir(parents=True, exist_ok=True)
    return path


def l1_dir(revision_dir: Path) -> Path:
    """Active-slice directory for a seeded single-L revision."""
    path = Path(revision_dir).resolve() / "L1"
    path.mkdir(parents=True, exist_ok=True)
    return path


def mark_focus_producer(revision_dir: Path, state: str = "Inductive") -> None:
    """Focus L: Inductive or Deductive (facts write)."""
    if state not in {"Inductive", "Deductive"}:
        raise ValueError(f"producer state must be Inductive or Deductive, got {state!r}")
    rev = Path(revision_dir).resolve()
    ledger = load_l_ledger(rev)
    focus = str(ledger["focus"])
    ledger["by_id"][focus]["state"] = state
    save_l_ledger(rev, ledger)


def lock_single_l1_tree(revision_dir: Path) -> None:
    """Compatibility name: seed a single-L ledger revision."""
    seed_l1_revision(revision_dir)


def init_working_ready(
    path: Path,
    *,
    mode: str,
    cycle_type: str = "feature",
    evaluate_round: int = 0,
) -> None:
    """Init session at Split, publish L1 ledger, advance to Working."""
    init_compose_session(
        path,
        mode=mode,
        cycle_type=cycle_type,
        evaluate_round=evaluate_round,
    )
    seed_l1_revision(path.parent)
    save_workflow_state(path, {"current_state": "Working"})


def mark_all_l_accepted(revision_dir: Path) -> None:
    """Set every ledger cell to Completed and unfrozen."""
    rev = Path(revision_dir).resolve()
    ledger = load_l_ledger(rev)
    for cell in ledger["by_id"].values():
        cell["state"] = "Completed"
        cell["frozen"] = False
    save_l_ledger(rev, ledger)


def mark_focus_intake_done(revision_dir: Path) -> None:
    """Focus L: Writing (ready for enter-evaluating)."""
    rev = Path(revision_dir).resolve()
    ledger = load_l_ledger(rev)
    focus = str(ledger["focus"])
    ledger["by_id"][focus]["state"] = "Writing"
    save_l_ledger(rev, ledger)
    stamp = rev / focus / "_writing.complete"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text("ok\n", encoding="utf-8")


def mark_focus_evaluating(revision_dir: Path) -> None:
    """Focus L: Evaluating with an active eval_run_id."""
    rev = Path(revision_dir).resolve()
    ledger = load_l_ledger(rev)
    focus = str(ledger["focus"])
    ledger["by_id"][focus]["state"] = "Evaluating"
    save_l_ledger(rev, ledger)
    slice_dir = rev / focus
    slice_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "eval_run_id": uuid.uuid4().hex,
        "ledger_fingerprint": ledger_fingerprint(load_l_ledger(rev)),
    }
    (slice_dir / "_eval_run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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
