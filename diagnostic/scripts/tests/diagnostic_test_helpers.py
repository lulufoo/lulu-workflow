"""Shared helpers for diagnostic script tests."""

from __future__ import annotations

import json
from pathlib import Path

from dx_decision_doc_schema import load_decision_doc
from dx_gate_payload_schema import gate_payload_path, load_gate_payload
from dx_session_integrity import render_decision_doc
from dx_workflow_common import decision_doc_path, gate_payloads_dir


def render_session_doc(project_root: Path, cycle_id: str, stage: str = "diagnostic") -> Path:
    return render_decision_doc(project_root, cycle_id, stage)


def load_rendered_doc(project_root: Path, cycle_id: str, stage: str = "diagnostic") -> str:
    render_session_doc(project_root, cycle_id, stage)
    return load_decision_doc(project_root / decision_doc_path(cycle_id, stage))


def load_gate_payload_file(
    project_root: Path,
    cycle_id: str,
    gate: str,
    stage: str = "diagnostic",
) -> dict:
    payloads_dir = project_root / gate_payloads_dir(cycle_id, stage)
    return load_gate_payload(gate_payload_path(payloads_dir, gate))


def gate_payload_exists(
    project_root: Path,
    cycle_id: str,
    gate: str,
    stage: str = "diagnostic",
) -> bool:
    payloads_dir = project_root / gate_payloads_dir(cycle_id, stage)
    return gate_payload_path(payloads_dir, gate).exists()


def list_gate_payloads(project_root: Path, cycle_id: str, stage: str = "diagnostic") -> list[str]:
    payloads_dir = project_root / gate_payloads_dir(cycle_id, stage)
    if not payloads_dir.exists():
        return []
    return sorted(path.stem for path in payloads_dir.glob("*.json"))
