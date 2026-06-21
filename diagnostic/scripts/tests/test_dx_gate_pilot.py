#!/usr/bin/env python3
"""Tests for diagnostic gate/register pilot (Q + E)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dx_decision_doc_schema import load_decision_doc  # noqa: E402
from dx_gate_control import (  # noqa: E402
    cmd_gate_close,
    cmd_init_session,
    cmd_invalidate_from,
    cmd_resolve_context,
)
from dx_register_control import cmd_register_append  # noqa: E402
from dx_workflow_common import decision_doc_path, gate_state_path, registers_path  # noqa: E402
from test_dx_gate_loop_a import _close_o  # noqa: E402


@pytest.fixture
def template_config(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / "skill-config" / "lulu-dev-workflow"
    cfg_dir.mkdir(parents=True)
    template = (
        "# Decision: {title}\n\n"
        "## 1. User Prior\n\n- placeholder\n\n"
        "## 2. Problem Definition\n\nTBD\n\n"
        "## 3. Direction Comparison\n\nTBD\n\n"
        "## 4. Decision Rationale\n\nTBD\n\n"
        "## 5. Scope\n\nTBD\n\n"
        "## 6. Assumptions & Risks\n\nTBD\n\n"
        "## 7. Execution Analysis\n\n### 7.1 Acceptance Criteria\n\nTBD\n"
    )
    local_template = tmp_path / "decision-doc.template.md"
    local_template.write_text(template, encoding="utf-8")
    cfg = {
        "diagnostic": {
            "decision_doc_template_url": local_template.as_uri(),
        }
    }
    cfg_path = cfg_dir / "workflow-config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path


def test_init_and_q_e_gate_close(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-test-001"
    stage = "diagnostic"

    monkeypatch.chdir(project_root)
    cache_root = project_root / ".cursor" / "lulu-dev-workflow"
    cache_root.mkdir(parents=True, exist_ok=True)

    assert cmd_init_session(project_root, cycle_id, stage) == 0

    assert cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="prior",
        payload={"kind": "excluded", "text": "排除方案 B"},
    ) == 0

    _close_o(project_root, cycle_id, stage)

    q_payload = {
        "problem_statement": "用户无法批量导出报表",
        "constraints": "必须兼容现有 SSO",
    }
    assert (
        cmd_gate_close(project_root, cycle_id, stage, "Q", q_payload) == 0
    )

    e_payload = {
        "directions": [
            {
                "name": "A",
                "approach": "服务端导出",
                "pros": "稳定",
                "cons": "慢",
                "recommended": True,
            },
            {
                "name": "B",
                "approach": "客户端导出",
                "pros": "快",
                "cons": "兼容性差",
                "recommended": False,
            },
        ],
        "excluded": [{"name": "C", "reason": "成本过高"}],
        "user_choice": "A",
    }
    assert cmd_gate_close(project_root, cycle_id, stage, "E", e_payload) == 0

    doc = load_decision_doc(project_root / decision_doc_path(cycle_id, stage))
    assert "用户无法批量导出报表" in doc
    assert "服务端导出" in doc
    assert "User Choice:** A" in doc

    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert registers["prior"][0]["source"] == "O"

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["gates"]["O"]["status"] == "closed"
    assert gate_state["gates"]["Q"]["status"] == "closed"
    assert gate_state["gates"]["E"]["status"] == "closed"
    assert gate_state["active_gate"] == "D"


def test_invalidate_from_e_resets_downstream(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-test-002"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)
    (project_root / ".cursor" / "lulu-dev-workflow").mkdir(parents=True, exist_ok=True)

    assert cmd_init_session(project_root, cycle_id, stage) == 0
    _close_o(project_root, cycle_id, stage)
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "Q",
        {"problem_statement": "problem", "constraints": "none"},
    )
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "E",
        {
            "directions": [
                {"name": "A", "approach": "a", "pros": "p", "cons": "c"},
                {"name": "B", "approach": "b", "pros": "p", "cons": "c"},
            ],
            "excluded": [],
            "user_choice": "A",
        },
    )

    assert cmd_invalidate_from(project_root, cycle_id, stage, "E") == 0

    doc = load_decision_doc(project_root / decision_doc_path(cycle_id, stage))
    direction_body = doc.split("## 3. Direction Comparison", 1)[1]
    assert "**User Choice:** TBD" in direction_body

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "E"
    assert gate_state["gates"]["E"]["status"] == "active"
    assert gate_state["gates"]["D"]["status"] == "invalidated"


def test_invalidate_from_q_clears_direction_section(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-test-004"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)
    (project_root / ".cursor" / "lulu-dev-workflow").mkdir(parents=True, exist_ok=True)

    cmd_init_session(project_root, cycle_id, stage)
    _close_o(project_root, cycle_id, stage)
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "Q",
        {"problem_statement": "problem", "constraints": "none"},
    )
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "E",
        {
            "directions": [
                {"name": "A", "approach": "a", "pros": "p", "cons": "c"},
                {"name": "B", "approach": "b", "pros": "p", "cons": "c"},
            ],
            "excluded": [],
            "user_choice": "A",
        },
    )

    assert cmd_invalidate_from(project_root, cycle_id, stage, "Q") == 0

    doc = load_decision_doc(project_root / decision_doc_path(cycle_id, stage))
    problem_body = doc.split("## 2. Problem Definition", 1)[1].split("## 3.", 1)[0]
    assert "TBD" in problem_body
    direction_body = doc.split("## 3. Direction Comparison", 1)[1]
    assert "**User Choice:** TBD" in direction_body


def test_gate_close_e_rejects_four_directions(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-test-005"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)
    (project_root / ".cursor" / "lulu-dev-workflow").mkdir(parents=True, exist_ok=True)

    cmd_init_session(project_root, cycle_id, stage)
    _close_o(project_root, cycle_id, stage)
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "Q",
        {"problem_statement": "problem", "constraints": "none"},
    )
    rc = cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "E",
        {
            "directions": [
                {"name": "A", "approach": "a", "pros": "p", "cons": "c"},
                {"name": "B", "approach": "b", "pros": "p", "cons": "c"},
                {"name": "C", "approach": "c", "pros": "p", "cons": "c"},
                {"name": "D", "approach": "d", "pros": "p", "cons": "c"},
            ],
            "excluded": [],
            "user_choice": "A",
        },
    )
    assert rc != 0


def test_resolve_context_empty_header_without_registers(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io
    from contextlib import redirect_stdout

    project_root = template_config
    cycle_id = "feature-test-006"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)
    (project_root / ".cursor" / "lulu-dev-workflow").mkdir(parents=True, exist_ok=True)

    cmd_init_session(project_root, cycle_id, stage)
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        rc = cmd_resolve_context(project_root, cycle_id, stage)
    assert rc == 0
    payload = json.loads(buffer.getvalue())
    assert payload["reply_header"] == ""


def test_resolve_context_includes_registers(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    from contextlib import redirect_stdout

    project_root = template_config
    cycle_id = "feature-test-003"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)
    (project_root / ".cursor" / "lulu-dev-workflow").mkdir(parents=True, exist_ok=True)

    cmd_init_session(project_root, cycle_id, stage)
    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="prior",
        payload={"kind": "preference", "text": "偏好渐进"},
    )

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        rc = cmd_resolve_context(project_root, cycle_id, stage)
    assert rc == 0
    payload = json.loads(buffer.getvalue())
    assert payload["reply_header"] == ""
    assert "偏好渐进" in payload["registers"]["prior"][0]["text"]


def test_init_session_starts_at_gate_o(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-test-o-init"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)
    (project_root / ".cursor" / "lulu-dev-workflow").mkdir(parents=True, exist_ok=True)

    assert cmd_init_session(project_root, cycle_id, stage) == 0
    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "O"
    assert gate_state["gates"]["O"]["status"] == "active"


def test_gate_close_o_advances_to_q(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-test-o-close"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)
    (project_root / ".cursor" / "lulu-dev-workflow").mkdir(parents=True, exist_ok=True)

    cmd_init_session(project_root, cycle_id, stage)
    _close_o(project_root, cycle_id, stage)
    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["gates"]["O"]["status"] == "closed"
    assert gate_state["active_gate"] == "Q"


def test_legacy_open_gate_id_normalizes(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dx_gate_state_schema import load_gate_state, save_gate_state

    project_root = template_config
    cycle_id = "feature-test-o-legacy"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)
    (project_root / ".cursor" / "lulu-dev-workflow").mkdir(parents=True, exist_ok=True)

    cmd_init_session(project_root, cycle_id, stage)
    path = project_root / gate_state_path(cycle_id, stage)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["active_gate"] = "open"
    raw["gates"]["open"] = raw["gates"].pop("O")
    path.write_text(json.dumps(raw), encoding="utf-8")

    normalized = load_gate_state(path)
    assert normalized["active_gate"] == "O"
    assert "open" not in normalized["gates"]
    save_gate_state(path, normalized)
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["active_gate"] == "O"
    assert "O" in reloaded["gates"]


def test_register_commit_g0_returns_full_ctx(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from dx_register_control import cmd_register_commit  # noqa: E402

    project_root = template_config
    cycle_id = "feature-register-commit"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)
    (project_root / ".cursor" / "lulu-dev-workflow").mkdir(parents=True, exist_ok=True)

    assert cmd_init_session(project_root, cycle_id, stage) == 0
    capsys.readouterr()

    assert (
        cmd_register_commit(
            project_root,
            cycle_id,
            stage,
            operations=[
                {
                    "action": "append",
                    "kind": "prior",
                    "payload": {"kind": "preference", "text": "Prefer incremental rollout"},
                },
                {
                    "action": "append",
                    "kind": "assumption",
                    "payload": {"text": "API is ready"},
                },
            ],
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["applied"] == 2
    assert payload["active_gate"] == "O"
    assert len(payload["registers"]["prior"]) == 1
    assert len(payload["registers"]["assumptions"]) == 1
    assert "gates" in payload
    assert "domain_constraints" in payload

    doc = load_decision_doc(project_root / decision_doc_path(cycle_id, stage))
    assert "Prefer incremental rollout" in doc
    assert "API is ready" in doc
