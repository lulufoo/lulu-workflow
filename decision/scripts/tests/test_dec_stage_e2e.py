#!/usr/bin/env python3
"""E2E smoke tests for lulu-bet and lulu-approach stage paths."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_domain_constraints_schema import load_domain_constraints  # noqa: E402
from dec_gate_control import cmd_init_session, cmd_resolve_context  # noqa: E402
from dec_workflow_common import (  # noqa: E402
    domain_constraints_path,
    gate_state_path,
    session_base_dir,
)
from test_dec_gate_loop_a import _full_template  # noqa: E402

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]


def _holder_constraints(stage: str) -> Path:
    return _WORKFLOW_ROOT / stage / "constraints-feature.json"


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


@pytest.mark.parametrize(
    ("stage", "expected_subdir"),
    [
        ("lulu-bet", "lulu-bet"),
        ("lulu-approach", "lulu-approach"),
    ],
)
def test_stage_init_and_constraints(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    expected_subdir: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = template_config
    cycle_id = f"e2e-{stage.replace('-', '_')}"
    constraints_path = _holder_constraints(stage)
    monkeypatch.chdir(project_root)

    assert (
        cmd_init_session(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
        )
        == 0
    )
    capsys.readouterr()
    session_dir = project_root / session_base_dir(
        cycle_id,
        stage,
        project_root=project_root,
        constraints_path=constraints_path,
    )
    assert expected_subdir in session_dir.as_posix()
    assert (session_dir / "gate-state.json").exists()

    assert (
        cmd_resolve_context(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
        )
        == 0
    )
    ctx = json.loads(capsys.readouterr().out)
    assert ctx["stage"] == stage
    assert ctx["domain_constraints"]["stage"] == stage
    assert ctx["domain_constraints"]["cache_subdir"] == expected_subdir
    assert "after_dc" in ctx

    if stage == "lulu-approach":
        constraints = load_domain_constraints(
            project_root / domain_constraints_path(
                cycle_id,
                stage,
                project_root=project_root,
                constraints_path=constraints_path,
            )
        )
        assert "impact_surface" in constraints["x_dimensions"]
        assert constraints.get("context") == {"sources": []}

    gate_state = json.loads(
        (project_root / gate_state_path(
            cycle_id,
            stage,
            project_root=project_root,
            constraints_path=constraints_path,
        )).read_text(encoding="utf-8")
    )
    assert gate_state["stage"] == stage


@pytest.mark.parametrize("stage", ["lulu-bet", "lulu-approach"])
def test_init_session_never_resolves_context_itself(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stage: str,
) -> None:
    """decision performs no path resolution of its own: the holder's own
    constraints-*.json template only ever carries an empty sources
    placeholder (context.sources is 100% auto-derived by the holder's own
    resolve_context.py, never by decision), so without an external
    --domain-constraints-file override, a session's saved context stays empty."""
    project_root = template_config
    cycle_id = f"e2e-noresolve-{stage.replace('-', '_')}"
    constraints_path = _holder_constraints(stage)
    monkeypatch.chdir(project_root)

    assert cmd_init_session(
        project_root, cycle_id, stage, constraints_path=constraints_path,
    ) == 0
    capsys.readouterr()
    assert cmd_resolve_context(
        project_root, cycle_id, stage, constraints_path=constraints_path,
    ) == 0
    ctx = json.loads(capsys.readouterr().out)
    assert ctx["context"] == {"sources": []}


@pytest.mark.parametrize(
    ("stage", "topic_stage"),
    [
        ("lulu-bet", "lulu-blueprint"),
        ("lulu-approach", "lulu-arch"),
    ],
)
def test_resolve_context_surfaces_preresolved_domain_override(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stage: str,
    topic_stage: str,
) -> None:
    """decision stores and reads back exactly what a holder's own resolver
    script (e.g. resolve_context.py) hands it via --domain-constraints-file —
    resolution itself happens entirely outside decision."""
    project_root = template_config
    cycle_id = f"e2e-topic-{stage.replace('-', '_')}"
    constraints_path = _holder_constraints(stage)
    monkeypatch.chdir(project_root)

    resolved_path = f"/cache/topic-line/{topic_stage}/revision1/{topic_stage}-doc.md"
    domain_override = {
        "context": {
            "sources": [
                {
                    "kind": "topic",
                    "loaded_message": "topic ctx",
                    "status": "loaded",
                    "resolved_doc_path": resolved_path,
                },
            ],
        },
    }

    assert cmd_init_session(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        domain_override=domain_override,
    ) == 0
    capsys.readouterr()
    assert cmd_resolve_context(
        project_root, cycle_id, stage, constraints_path=constraints_path,
    ) == 0
    ctx = json.loads(capsys.readouterr().out)
    sources = ctx["context"]["sources"]
    topic_sources = [s for s in sources if s["kind"] == "topic"]
    assert len(topic_sources) == 1
    assert topic_sources[0]["status"] == "loaded"
    assert topic_sources[0]["resolved_doc_path"] == resolved_path


@pytest.mark.parametrize(
    ("stage", "topic_stage"),
    [
        ("lulu-bet", "lulu-blueprint"),
        ("lulu-approach", "lulu-arch"),
    ],
)
def test_domain_override_context_frozen_after_init(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stage: str,
    topic_stage: str,
) -> None:
    """Once a pre-resolved context is handed in at init via
    --domain-constraints-file, it is frozen into the session's own
    domain-constraints.json copy — resolve-context must keep returning
    exactly that, regardless of anything happening on disk afterward,
    because decision never re-resolves (it has no resolution code at all)."""
    from dec_workflow_common import CACHE_DIR

    project_root = template_config
    cycle_id = f"e2e-topic-frozen-{stage.replace('-', '_')}"
    topic_id = "topic-20260101000000-aabbccdd"
    constraints_path = _holder_constraints(stage)
    monkeypatch.chdir(project_root)

    cache_dir = project_root / CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    cj = cache_dir / "cycles.json"
    cj.write_text(json.dumps({
        cycle_id: {"name": "feature", "topic_id": topic_id},
        topic_id: {"name": "topic"},
    }), encoding="utf-8")
    topic_doc_dir = cache_dir / topic_id / topic_stage / "revision1"
    topic_doc_dir.mkdir(parents=True, exist_ok=True)
    topic_doc = topic_doc_dir / f"{topic_stage}-doc.md"
    topic_doc.write_text("# topic doc\n", encoding="utf-8")

    domain_override = {
        "context": {
            "sources": [
                {
                    "kind": "topic",
                    "loaded_message": "topic ctx",
                    "status": "loaded",
                    "resolved_doc_path": str(topic_doc.resolve()),
                },
            ],
        },
    }

    assert cmd_init_session(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        domain_override=domain_override,
    ) == 0
    capsys.readouterr()

    # Simulate the topic doc vanishing (e.g. topic cycle got reopened/rewritten)
    # after this feature's decision session was initialized.
    topic_doc.unlink()

    assert cmd_resolve_context(
        project_root, cycle_id, stage, constraints_path=constraints_path,
    ) == 0
    ctx = json.loads(capsys.readouterr().out)
    sources = ctx["context"]["sources"]
    topic_sources = [s for s in sources if s["kind"] == "topic"]
    assert len(topic_sources) == 1
    assert topic_sources[0]["status"] == "loaded"
    assert topic_sources[0]["resolved_doc_path"] == str(topic_doc.resolve())
