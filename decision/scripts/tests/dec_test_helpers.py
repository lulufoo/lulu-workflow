"""Shared helpers for decision script tests."""

from __future__ import annotations

from pathlib import Path

from dec_decision_doc_schema import load_decision_doc
from dec_gate_payload_schema import gate_payload_path, load_gate_payload
from dec_session_integrity import render_decision_doc
from dec_session_paths import resolve_session_root_for_command, session_artifact_paths
from dec_workflow_common import CACHE_DIR


def full_decision_doc_template() -> str:
    """Minimal decision-doc skeleton matching Settled Direction layout."""
    return (
        "# Decision: {title}\n\n"
        "## 1. User Prior\n\n- placeholder\n\n"
        "## 2. Problem Definition\n\nTBD\n\n"
        "## 3. Direction Readiness\n\nTBD\n\n## 4. Direction Comparison\n\nTBD\n\n"
        "## 5. Settled Direction\n\n"
        "### Decision Rationale\n\nTBD\n\n"
        "### Scope\n\n"
        "**Applies to:** TBD\n\n"
        "**Explicitly excludes:** TBD\n\n"
        "### Landing Approach\n\nTBD\n\n"
        "## 6. Assumptions & Risks\n\nTBD\n\n"
        "## 7. Execution Analysis\n\n### 7.1 Acceptance Criteria\n\nTBD\n"
    )


def _active_paths(project_root: Path, cycle_id: str, stage: str) -> dict[str, Path]:
    root = resolve_session_root_for_command(
        project_root,
        cycle_id,
        stage,
        CACHE_DIR,
    )
    return session_artifact_paths(root)


def render_session_doc(project_root: Path, cycle_id: str, stage: str = "decision") -> Path:
    return render_decision_doc(project_root, cycle_id, stage)


def load_rendered_doc(project_root: Path, cycle_id: str, stage: str = "decision") -> str:
    render_session_doc(project_root, cycle_id, stage)
    paths = _active_paths(project_root, cycle_id, stage)
    return load_decision_doc(paths["decision_doc"])


def load_gate_payload_file(
    project_root: Path,
    cycle_id: str,
    gate: str,
    stage: str = "decision",
) -> dict:
    paths = _active_paths(project_root, cycle_id, stage)
    return load_gate_payload(gate_payload_path(paths["payloads_dir"], gate))


def gate_payload_exists(
    project_root: Path,
    cycle_id: str,
    gate: str,
    stage: str = "decision",
) -> bool:
    paths = _active_paths(project_root, cycle_id, stage)
    return gate_payload_path(paths["payloads_dir"], gate).exists()


def risk_for_source(registers: dict, source_id: str) -> dict:
    for entry in registers.get("risks") or []:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("source_ref") if isinstance(entry.get("source_ref"), dict) else {}
        if str(ref.get("id")) == source_id:
            return entry
    raise AssertionError(f"no RK# for {source_id}: {registers.get('risks')}")


def list_gate_payloads(project_root: Path, cycle_id: str, stage: str = "decision") -> list[str]:
    paths = _active_paths(project_root, cycle_id, stage)
    payloads_dir = paths["payloads_dir"]
    if not payloads_dir.exists():
        return []
    return sorted(path.stem for path in payloads_dir.glob("*.json"))
