"""Shared helpers for start / draft integration tests."""

from __future__ import annotations

from pathlib import Path

from delivered_refs_schema import DeliveredRef, record_delivered_ref
from start_scope_helpers import first_ref
from session_state_schema import bump_active_doc
from workflow_common import CACHE_DIR
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID
from workflow_profile_paths import state_path
from workflow_state_schema import init_drafting


def product_delivered_refs(product_path: str = "/p.md") -> list[DeliveredRef]:
    return [DeliveredRef(type="product-spec", path=product_path)]


def tech_diagnostic_refs(decision_path: Path | str) -> list[DeliveredRef]:
    return [DeliveredRef(type="tech-diagnostic", path=str(Path(decision_path).resolve()))]


def tech_plan_scope_refs(delivered_refs: list[DeliveredRef]) -> list[DeliveredRef]:
    out: list[DeliveredRef] = []
    primary = first_ref(delivered_refs, "tech-design") or first_ref(
        delivered_refs,
        "tech-diagnostic",
    )
    if primary is not None:
        out.append(primary)
    product = first_ref(delivered_refs, "product-spec")
    if product is not None:
        out.append(product)
    return out


def tech_design_scope_refs(delivered_refs: list[DeliveredRef]) -> list[DeliveredRef]:
    primary = first_ref(delivered_refs, "tech-diagnostic")
    return [primary] if primary is not None else []


def product_spec_scope_refs(delivered_refs: list[DeliveredRef]) -> list[DeliveredRef]:
    primary = first_ref(delivered_refs, "product-diagnostic")
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
    diag_dir = cache_dir / cycle_id / "tech" / "diagnostic"
    diag_dir.mkdir(parents=True, exist_ok=True)
    decision = diag_dir / "decision-doc.md"
    decision.write_text("# Decision\n", encoding="utf-8")
    refs = delivered_refs
    if refs is None:
        refs = [DeliveredRef(type="tech-diagnostic", path=str(decision.resolve()))]
    seed_delivered_refs_file(project_root, cycle_id, refs)
    active_doc = bump_active_doc(cycle_id, project_root, profile_id)
    ws_path = project_root / state_path(cycle_id, active_doc, profile_id)
    scope_refs = tech_plan_scope_refs(refs)
    init_drafting(ws_path, mode=mode, delivered_refs=refs, scope_refs=scope_refs)
    return ws_path
