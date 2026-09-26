#!/usr/bin/env python3
"""Tests for decision bind_session / freeze_session public lifecycle API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG = Path(__file__).resolve().parents[1]
if str(_DIAG) not in sys.path:
    sys.path.insert(0, str(_DIAG))

from dec_active_session_schema import load_active_session  # noqa: E402
from dec_domain_constraints_schema import load_domain_constraints  # noqa: E402
from dec_lifecycle import (  # noqa: E402
    bind_session,
    freeze_session,
    unfreeze_session_public,
)
from dec_session_paths import stage_outer_root  # noqa: E402
from dec_session_state_schema import read_current_state, session_state_file  # noqa: E402
from dec_workflow_common import CACHE_DIR, session_base_dir  # noqa: E402
from test_dec_gate_loop_a import _full_template  # noqa: E402


@pytest.fixture
def template_config(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / ".cursor" / "lulu-workflow"
    cfg_dir.mkdir(parents=True)
    local_template = tmp_path / "decision-doc.template.md"
    local_template.write_text(_full_template(), encoding="utf-8")
    (cfg_dir / "workflow-config.json").write_text(
        json.dumps({"decision": {"decision_doc_template_url": local_template.as_uri()}}),
        encoding="utf-8",
    )
    return tmp_path


def _write_resolved(path: Path, docs: dict[str, str] | None = None) -> Path:
    payload = {"context": {"docs": docs or {"product_spec": "/tmp/spec.md"}}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_bind_session_initialize(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    monkeypatch.chdir(project_root)
    cycle_id = "feature-bind-init-001"
    stage = "decision"
    outer = project_root / session_base_dir(cycle_id, stage, project_root=project_root)
    nested = outer / "D1"
    resolved = _write_resolved(outer / "bindings" / "b1" / "resolved-context.json")

    result = bind_session(
        project_root,
        cycle_id,
        session_dir=nested,
        resolved_context_path=resolved,
        mode="initialize",
    )
    assert result["ok"] is True
    assert result["initialized"] is True
    assert Path(result["session_dir"]).resolve() == nested.resolve()
    assert (nested / "gate-state.json").is_file()
    assert read_current_state(session_state_file(nested)) == "InProgress"
    active = load_active_session(stage_outer_root(project_root, cycle_id, stage, CACHE_DIR))
    assert active["session_dir"] == "D1"
    dc = load_domain_constraints(nested / "domain-constraints.json")
    assert dc["context"]["docs"]["product_spec"] == "/tmp/spec.md"


def test_bind_session_existing_refreshes_context_before_active(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    monkeypatch.chdir(project_root)
    cycle_id = "feature-bind-exist-001"
    stage = "decision"
    outer = project_root / session_base_dir(cycle_id, stage, project_root=project_root)
    nested = outer / "D1"
    r1 = _write_resolved(outer / "bindings" / "b1" / "resolved-context.json")
    bind_session(
        project_root,
        cycle_id,
        session_dir=nested,
        resolved_context_path=r1,
        mode="initialize",
    )
    r2 = _write_resolved(
        outer / "bindings" / "b2" / "resolved-context.json",
        docs={"product_spec": "/tmp/spec-v2.md"},
    )
    result = bind_session(
        project_root,
        cycle_id,
        session_dir=nested,
        resolved_context_path=r2,
        mode="existing",
    )
    assert result["initialized"] is False
    assert result["context_docs"]["product_spec"] == "/tmp/spec-v2.md"
    dc = load_domain_constraints(nested / "domain-constraints.json")
    assert dc["context"]["docs"]["product_spec"] == "/tmp/spec-v2.md"
    active = load_active_session(stage_outer_root(project_root, cycle_id, stage, CACHE_DIR))
    assert active["session_dir"] == "D1"


def test_freeze_and_unfreeze_session(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    monkeypatch.chdir(project_root)
    cycle_id = "feature-bind-freeze-001"
    stage = "decision"
    outer = project_root / session_base_dir(cycle_id, stage, project_root=project_root)
    nested = outer / "D1"
    resolved = _write_resolved(outer / "bindings" / "b1" / "resolved-context.json")
    bind_session(
        project_root,
        cycle_id,
        session_dir=nested,
        resolved_context_path=resolved,
        mode="initialize",
    )
    prior = freeze_session(nested)
    assert prior == "InProgress"
    assert read_current_state(session_state_file(nested)) == "Frozen"
    assert unfreeze_session_public(nested) is True
    assert read_current_state(session_state_file(nested)) == "InProgress"


def test_bind_session_existing_refresh_failure_keeps_prior_active(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    monkeypatch.chdir(project_root)
    cycle_id = "feature-bind-refresh-fail-001"
    stage = "decision"
    outer = project_root / session_base_dir(cycle_id, stage, project_root=project_root)
    d1 = outer / "D1"
    d2 = outer / "D2"
    r1 = _write_resolved(outer / "bindings" / "b1" / "resolved-context.json")
    bind_session(
        project_root,
        cycle_id,
        session_dir=d1,
        resolved_context_path=r1,
        mode="initialize",
    )
    r2 = _write_resolved(
        outer / "bindings" / "b2" / "resolved-context.json",
        docs={"product_spec": "/tmp/d2.md"},
    )
    bind_session(
        project_root,
        cycle_id,
        session_dir=d2,
        resolved_context_path=r2,
        mode="initialize",
    )
    assert load_active_session(stage_outer_root(project_root, cycle_id, stage, CACHE_DIR))[
        "session_dir"
    ] == "D2"

    def fail_refresh(_: Path, __: dict[str, object]) -> dict[str, str]:
        raise OSError("simulated context write failure")

    monkeypatch.setattr("dec_lifecycle._refresh_session_context", fail_refresh)
    with pytest.raises(OSError, match="simulated context write failure"):
        bind_session(
            project_root,
            cycle_id,
            session_dir=d1,
            resolved_context_path=r1,
            mode="existing",
        )
    assert load_active_session(stage_outer_root(project_root, cycle_id, stage, CACHE_DIR))[
        "session_dir"
    ] == "D2"


def test_commit_active_does_not_mutate_domain_constraints(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dec_active_control import _commit_active

    project_root = template_config
    monkeypatch.chdir(project_root)
    cycle_id = "feature-commit-active-pure-001"
    stage = "decision"
    outer = project_root / session_base_dir(cycle_id, stage, project_root=project_root)
    nested = outer / "D1"
    resolved = _write_resolved(outer / "bindings" / "b1" / "resolved-context.json")
    bind_session(
        project_root,
        cycle_id,
        session_dir=nested,
        resolved_context_path=resolved,
        mode="initialize",
    )
    before = (nested / "domain-constraints.json").read_text(encoding="utf-8")
    result = _commit_active(project_root, cycle_id, stage, session_dir=nested)
    assert "context_docs" not in result
    after = (nested / "domain-constraints.json").read_text(encoding="utf-8")
    assert before == after


def test_set_active_cli_removed(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dec_active_control import main as active_main

    project_root = template_config
    monkeypatch.chdir(project_root)
    with pytest.raises(SystemExit):
        active_main(
            [
                "--project-root",
                str(project_root),
                "--cycle-id",
                "feature-no-set-active",
                "set-active",
                "--session-dir",
                "unused",
            ]
        )
