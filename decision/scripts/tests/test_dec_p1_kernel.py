#!/usr/bin/env python3
"""P1 decision kernel: Frozen session state, $DEC_REOPEN, --session-dir."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_domain_constraints_schema import (  # noqa: E402
    load_domain_constraints,
    normalize_domain_constraints,
)
from dec_gate_control import (  # noqa: E402
    cmd_gate_close,
    cmd_init_session,
    cmd_reopen,
    cmd_rs_commit,
    main as gate_main,
)
from dec_gate_state_schema import load_gate_state  # noqa: E402
from dec_register_control import main as register_main  # noqa: E402
from dec_register_schema import load_registers  # noqa: E402
from dec_session_paths import parse_session_dir_arg  # noqa: E402
from dec_session_state_schema import (  # noqa: E402
    read_current_state,
    session_state_file,
    write_session_state,
)
from dec_workflow_common import session_base_dir  # noqa: E402
from test_dec_gate_loop_a import _close_qe, _full_template  # noqa: E402

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_START_PY = _DIAG_SCRIPTS / "dec_start.py"
_REOPEN_PY = _DIAG_SCRIPTS / "dec_reopen.py"
_SUBPROCESS_ENV = {**os.environ}


@pytest.fixture
def template_config(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / "skill-config" / "lulu-dev-workflow"
    cfg_dir.mkdir(parents=True)
    local_template = tmp_path / "decision-doc.template.md"
    local_template.write_text(_full_template(), encoding="utf-8")
    (cfg_dir / "workflow-config.json").write_text(
        json.dumps({"decision": {"decision_doc_template_url": local_template.as_uri()}}),
        encoding="utf-8",
    )
    return tmp_path


def test_session_can_enter_frozen(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-p1-frozen-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    assert cmd_init_session(project_root, cycle_id, stage) == 0
    session_dir = project_root / session_base_dir(cycle_id, stage)
    ss = session_state_file(session_dir)
    write_session_state(ss, "InProgress")
    assert read_current_state(ss) == "InProgress"

    write_session_state(ss, "Frozen")
    assert read_current_state(ss) == "Frozen"


def test_reopen_sets_frozen_from_delivered(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-p1-reopen-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    assert cmd_init_session(project_root, cycle_id, stage) == 0
    session_dir = project_root / session_base_dir(cycle_id, stage)
    ss = session_state_file(session_dir)
    write_session_state(ss, "Delivered")

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_reopen(project_root, cycle_id, stage)
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert payload["ok"] is True
    assert payload["session_state"] == "Frozen"
    assert payload["prior_state"] == "Delivered"
    assert read_current_state(ss) == "Frozen"


def test_reopen_cli_sets_frozen(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-p1-reopen-cli-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    assert cmd_init_session(project_root, cycle_id, stage) == 0
    session_dir = project_root / session_base_dir(cycle_id, stage)
    write_session_state(session_state_file(session_dir), "Delivered")

    result = subprocess.run(
        [
            sys.executable,
            str(_REOPEN_PY),
            "--project-root",
            str(project_root),
            "--cycle-id",
            cycle_id,
            "--stage",
            stage,
        ],
        capture_output=True,
        text=True,
        env=_SUBPROCESS_ENV,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["session_state"] == "Frozen"
    assert read_current_state(session_state_file(session_dir)) == "Frozen"


def test_frozen_rejects_gate_close_until_rs_commit(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import contextlib

    project_root = template_config
    cycle_id = "feature-p1-frozen-guard-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    assert cmd_init_session(project_root, cycle_id, stage) == 0
    _close_qe(project_root, cycle_id, stage)
    session_dir = project_root / session_base_dir(cycle_id, stage)
    write_session_state(session_state_file(session_dir), "Delivered")
    assert cmd_reopen(project_root, cycle_id, stage) == 0
    assert read_current_state(session_state_file(session_dir)) == "Frozen"

    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr), redirect_stdout(io.StringIO()):
        rc = cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "D",
            {
                "decision_rationale": "x",
                "applies_to": "a",
                "excludes": "b",
                "execution_approach": "c",
            },
        )
    assert rc == 1
    assert "Frozen" in stderr.getvalue()

    out = io.StringIO()
    with redirect_stdout(out):
        rc = cmd_rs_commit(project_root, cycle_id, stage, "Q", operations=[])
    assert rc == 0
    payload = json.loads(out.getvalue())
    assert payload["unfroze"] is True
    assert read_current_state(session_state_file(session_dir)) == "InProgress"
    gate_state = load_gate_state(session_dir / "gate-state.json")
    assert gate_state["gates"]["Q"]["status"] == "stale"


def test_in_session_rs_commit_does_not_require_frozen(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P1.5a R1: G9→RS stays InProgress; rs-commit only marks gate stale."""
    project_root = template_config
    cycle_id = "feature-p1-g9-stale-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    assert cmd_init_session(project_root, cycle_id, stage) == 0
    _close_qe(project_root, cycle_id, stage)
    session_dir = project_root / session_base_dir(cycle_id, stage)
    write_session_state(session_state_file(session_dir), "InProgress")

    out = io.StringIO()
    with redirect_stdout(out):
        rc = cmd_rs_commit(project_root, cycle_id, stage, "Q", operations=[])
    assert rc == 0
    payload = json.loads(out.getvalue())
    assert payload["unfroze"] is False
    assert read_current_state(session_state_file(session_dir)) == "InProgress"
    assert payload.get("session_state") == "InProgress"


def test_parse_session_dir_arg_relative_and_absolute(tmp_path: Path) -> None:
    project_root = tmp_path
    nested = project_root / "cache" / "c1" / "lulu-approach" / "main"
    nested.mkdir(parents=True)
    parsed = parse_session_dir_arg("cache/c1/lulu-approach/main", project_root)
    assert parsed == nested.resolve()
    parsed_abs = parse_session_dir_arg(str(nested), project_root)
    assert parsed_abs == nested.resolve()
    assert parse_session_dir_arg("", project_root) is None


def test_start_with_session_dir_nested_root(template_config: Path) -> None:
    project_root = template_config
    cycle_id = "feature-p1-session-dir-001"
    outer = project_root / session_base_dir(cycle_id, "decision", project_root=project_root)
    nested = outer / "main"
    nested.mkdir(parents=True)

    result = subprocess.run(
        [
            sys.executable,
            str(_START_PY),
            "--project-root",
            str(project_root),
            "--cycle-id",
            cycle_id,
            "--stage",
            "decision",
            "--session-dir",
            str(nested),
        ],
        capture_output=True,
        text=True,
        env=_SUBPROCESS_ENV,
    )
    assert result.returncode == 0, result.stderr
    assert (nested / "gate-state.json").exists()
    assert (nested / "domain-constraints.json").exists()
    assert read_current_state(session_state_file(nested)) == "InProgress"
    assert (outer / "active-session.json").is_file()
    active = json.loads((outer / "active-session.json").read_text(encoding="utf-8"))
    assert active["session_dir"] == "main"


def test_gate_control_cli_uses_active_session(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nested Dx: set Active then resolve-context without --session-dir."""
    from dec_active_control import set_active_session
    from dec_workflow_common import CACHE_DIR, session_base_dir

    project_root = template_config
    cycle_id = "feature-p1-gc-session-dir-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    outer = project_root / session_base_dir(cycle_id, stage, project_root=project_root)
    nested = outer / "D1"
    assert (
        cmd_init_session(
            project_root,
            cycle_id,
            stage,
            session_dir=nested,
            domain_override={
                "node_id": "D1",
                "session_role": "sub",
            },
        )
        == 0
    )
    write_session_state(session_state_file(nested), "InProgress")
    set_active_session(project_root, cycle_id, stage, session_dir=nested)

    rc = gate_main(
        [
            "--project-root",
            str(project_root),
            "--cycle-id",
            cycle_id,
            "--stage",
            stage,
            "resolve-context",
        ]
    )
    assert rc == 0
    constraints = load_domain_constraints(nested / "domain-constraints.json")
    assert constraints["node_id"] == "D1"
    assert constraints["session_role"] == "sub"


def test_register_control_cli_uses_active_session(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nested D1: set Active then register-commit without --session-dir."""
    from dec_active_control import set_active_session
    from dec_workflow_common import session_base_dir

    project_root = template_config
    cycle_id = "feature-p1-reg-session-dir-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    outer = project_root / session_base_dir(cycle_id, stage, project_root=project_root)
    nested = outer / "D1"
    assert (
        cmd_init_session(
            project_root,
            cycle_id,
            stage,
            session_dir=nested,
            domain_override={
                "node_id": "D1",
                "session_role": "sub",
            },
        )
        == 0
    )
    write_session_state(session_state_file(nested), "InProgress")
    set_active_session(project_root, cycle_id, stage, session_dir=nested)

    ops = json.dumps(
        [
            {
                "action": "append",
                "kind": "prior",
                "payload": {"kind": "preference", "text": "nested prior via active"},
            }
        ]
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = register_main(
            [
                "--project-root",
                str(project_root),
                "--cycle-id",
                cycle_id,
                "--stage",
                stage,
                "register-commit",
                "--operations",
                ops,
            ]
        )
    assert rc == 0, buf.getvalue()
    payload = json.loads(buf.getvalue())
    assert payload["ok"] is True
    assert payload["applied"] == 1

    registers = load_registers(nested / "registers.json", r_gate_closed=False)
    assert any(
        e.get("text") == "nested prior via active" for e in registers.get("prior", [])
    )

def test_domain_constraints_preserves_node_id_session_role() -> None:
    data = normalize_domain_constraints(
        {
            "version": "1",
            "stage": "lulu-approach",
            "cache_subdir": "lulu-approach",
            "omitted_sections": [],
            "x_dimensions": ["acceptance_criteria"],
            "objective": "plan approach",
            "domain": {"name": "approach", "instruction": "do approach"},
            "node_id": "main",
            "session_role": "main",
        }
    )
    assert data["node_id"] == "main"
    assert data["session_role"] == "main"
