#!/usr/bin/env python3
"""Tests for legacy session migration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_gate_control import cmd_migrate_session  # noqa: E402
from dec_gate_state_schema import load_gate_state  # noqa: E402
from dec_migrate_session import needs_migration  # noqa: E402
from dec_register_schema import load_registers  # noqa: E402
from dec_workflow_common import (  # noqa: E402
    gate_state_path,
    registers_path,
    session_base_dir,
    session_state_path,
)
from test_dec_gate_loop_a import _full_template  # noqa: E402


def _write_legacy_session(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    doc_body: str,
    state: str = "InProgress",
) -> Path:
    session_dir = project_root / session_base_dir(cycle_id, stage)
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session-state.md").write_text(
        f"---\nversion: 1\ncurrent_state: {state}\nupdated_at: 2026-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    (session_dir / "decision-doc.md").write_text(doc_body, encoding="utf-8")
    return session_dir


@pytest.fixture
def template_config(tmp_path: Path) -> Path:
    return tmp_path


def test_needs_migration_detects_legacy(template_config: Path) -> None:
    session_dir = _write_legacy_session(
        template_config,
        "legacy-001",
        "decision",
        doc_body=_full_template().replace("{title}", "T").replace("{one-line summary of the intent input}", "c"),
    )
    assert needs_migration(session_dir) is True


def test_migrate_in_progress_infers_active_gate(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = template_config
    cycle_id = "legacy-002"
    stage = "decision"
    monkeypatch.chdir(project_root)

    doc = _full_template().replace("{title}", "T").replace("{one-line summary of the intent input}", "c")
    doc = doc.replace("TBD", "filled", 3)
    _write_legacy_session(project_root, cycle_id, stage, doc_body=doc)

    assert cmd_migrate_session(project_root, cycle_id, stage) == 0

    gate_state = load_gate_state(project_root / gate_state_path(cycle_id, stage))
    assert gate_state["active_gate"] == "D"
    registers = load_registers(project_root / registers_path(cycle_id, stage), r_gate_closed=False)
    assert registers["assumptions"] == []


def test_migrate_delivered_closes_all_gates(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = template_config
    cycle_id = "legacy-003"
    stage = "decision"
    monkeypatch.chdir(project_root)

    doc = _full_template().replace("{title}", "T").replace("{one-line summary of the intent input}", "c")
    assumptions_section = (
        "## 6. Assumptions & Risks\n\n"
        "| # | Assumption | Source | Risk | Class | Release Tracking | Failure Consequence | Verification | Status |\n"
        "|---|-----------|--------|------|-------|------------------|---------------------|-------------|--------|\n"
        "| A1 | API ready | X | L | decision | | minor | Accepted | [已验证] |\n"
        "| A2 | SDK embed | X | H | implementation | | blocked | Accepted | [已交接] |\n"
    )
    doc = doc.replace("## 6. Assumptions & Risks\n\nTBD", assumptions_section.strip())
    doc = doc.replace("## 3. Direction Readiness\n\nTBD\n\n", "")
    doc = (
        doc.replace("## 7. Execution Analysis", "## 6. Execution Analysis")
        .replace("## 6. Assumptions & Risks", "## 5. Assumptions & Risks")
        .replace("## 5. Settled Direction", "## 4. Settled Direction")
        .replace("## 4. Direction Comparison", "## 3. Direction Comparison")
    )
    while "TBD" in doc:
        doc = doc.replace("TBD", "done", 1)

    _write_legacy_session(project_root, cycle_id, stage, doc_body=doc, state="Delivered")

    assert cmd_migrate_session(project_root, cycle_id, stage) == 0

    gate_state = load_gate_state(project_root / gate_state_path(cycle_id, stage))
    assert gate_state["active_gate"] == "DC"
    assert gate_state["gates"]["DC"]["status"] == "closed"
    assert "GL" in gate_state["skipped_gates"]
    migrated_constraints = json.loads(
        (project_root / session_base_dir(cycle_id, stage) / "domain-constraints.json").read_text(
            encoding="utf-8"
        )
    )
    assert "direction_readiness" in migrated_constraints["omitted_sections"]

    registers = load_registers(project_root / registers_path(cycle_id, stage), r_gate_closed=True)
    assert len(registers["assumptions"]) == 2
    assert registers["assumptions"][0]["id"] == "A1"
    assert registers["assumptions"][0]["risk_state"] == "completed"
    assert registers["assumptions"][0]["risk_class"] == "decision"
    assert registers["assumptions"][0]["release_terms"] == "Accepted"
    assert registers["assumptions"][1]["id"] == "A2"
    assert registers["assumptions"][1]["risk_state"] == "open"
    assert registers["assumptions"][1]["risk_class"] == "implementation"
    assert registers["assumptions"][1]["release_terms"] == "Accepted"


def test_migrate_via_start_writes_cycle_state(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os
    import subprocess

    project_root = template_config
    cycle_id = "legacy-start-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    doc = _full_template().replace("{title}", "T").replace("{one-line summary of the intent input}", "c")
    doc = doc.replace("TBD", "filled", 2)
    session_dir = project_root / ".cache/copilot/lulu-dev-workflow" / cycle_id / "decision"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session-state.md").write_text(
        "---\nversion: 1\ncurrent_state: InProgress\nupdated_at: 2026-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    (session_dir / "decision-doc.md").write_text(doc, encoding="utf-8")

    env = {**os.environ, "LULU_PLATFORM": "copilot"}
    start_py = _DIAG_SCRIPTS / "dec_start.py"
    result = subprocess.run(
        [
            sys.executable,
            str(start_py),
            "--project-root",
            str(project_root),
            "--cycle-id",
            cycle_id,
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr

    cycle_state = project_root / ".cache/copilot/lulu-dev-workflow" / cycle_id / "cycle-state.json"
    assert cycle_state.is_file()
    payload = json.loads(cycle_state.read_text(encoding="utf-8"))
    assert payload["current_stage"] == stage
