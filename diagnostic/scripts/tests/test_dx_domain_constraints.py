#!/usr/bin/env python3
"""Tests for domain constraints filtering and release_tracking in decision-doc."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dx_decision_doc_schema import load_decision_doc  # noqa: E402
from dx_domain_constraints_schema import load_domain_constraints  # noqa: E402
from dx_gate_control import cmd_gate_close, cmd_init_session, cmd_resolve_context  # noqa: E402
from dx_register_control import cmd_register_append, cmd_register_update  # noqa: E402
from dx_workflow_common import decision_doc_path, domain_constraints_path  # noqa: E402
from test_dx_gate_loop_a import _close_qe, _full_template  # noqa: E402


@pytest.fixture
def template_config(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / "skill-config" / "lulu-dev-workflow"
    cfg_dir.mkdir(parents=True)
    local_template = tmp_path / "decision-doc.template.md"
    local_template.write_text(_full_template(), encoding="utf-8")
    cfg_path = cfg_dir / "workflow-config.json"
    cfg_path.write_text(
        json.dumps({"diagnostic": {"decision_doc_template_url": local_template.as_uri()}}),
        encoding="utf-8",
    )
    return tmp_path


_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]


def _holder_constraints(stage: str) -> Path:
    return _WORKFLOW_ROOT / stage / "constraints.json"


def test_init_strips_omitted_sections(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-domain-001"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)

    assert (
        cmd_init_session(
            project_root,
            cycle_id,
            stage,
            domain_override={"omitted_sections": ["scope", "execution_analysis"]},
        )
        == 0
    )

    doc = load_decision_doc(project_root / decision_doc_path(cycle_id, stage))
    assert "## 5. Scope" not in doc
    assert "## 7. Execution Analysis" not in doc
    assert "## 4. Decision Rationale" in doc

    constraints = load_domain_constraints(project_root / domain_constraints_path(cycle_id, stage))
    assert "scope" in constraints["omitted_sections"]


def test_x_gate_close_respects_x_dimensions(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-domain-002"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)

    cmd_init_session(
        project_root,
        cycle_id,
        stage,
        domain_override={
            "omitted_sections": [],
            "x_dimensions": ["acceptance_criteria", "gap_check"],
        },
    )
    _close_qe(project_root, cycle_id, stage)
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "D",
        {
            "decision_rationale": "rationale",
            "applies_to": "scope",
            "excludes": "none",
            "execution_approach": "serial",
        },
    )

    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "X",
            {
                "acceptance_criteria": "Users can export",
                "gap": "None",
            },
        )
        == 0
    )

    doc = load_decision_doc(project_root / decision_doc_path(cycle_id, stage))
    assert "Users can export" in doc
    assert "### 7.2 Impact Surface" not in doc
    assert "### 7.4 Implementation Sketch" not in doc
    assert "**Gap (if any):** None" in doc


def test_release_tracking_column_in_assumptions_table(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = template_config
    cycle_id = "feature-domain-003"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)

    cmd_init_session(project_root, cycle_id, stage)
    _close_qe(project_root, cycle_id, stage)
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "D",
        {
            "decision_rationale": "r",
            "applies_to": "s",
            "excludes": "n",
            "execution_approach": "e",
        },
    )
    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="assumption",
        payload={"text": "Tracked item"},
    )
    cmd_register_update(
        project_root,
        cycle_id,
        stage,
        entry_id="A1",
        payload={"release_tracking": True},
    )

    doc = load_decision_doc(project_root / decision_doc_path(cycle_id, stage))
    assert "Release Tracking" in doc
    assert "Yes" in doc
    assert "Tracked item" in doc


def test_resolve_context_includes_domain_constraints(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = template_config
    cycle_id = "feature-domain-004"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)

    assert cmd_init_session(project_root, cycle_id, stage) == 0
    captured = capsys.readouterr()
    assert cmd_resolve_context(project_root, cycle_id, stage) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "domain_constraints" in payload
    assert "x_dimensions" in payload["domain_constraints"]


def test_resolve_context_includes_role_for_product_diagnostic(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = template_config
    cycle_id = "feature-domain-role"
    stage = "product-diagnostic"
    monkeypatch.chdir(project_root)

    assert (
        cmd_init_session(
            project_root,
            cycle_id,
            stage,
            constraints_path=_holder_constraints(stage),
        )
        == 0
    )
    capsys.readouterr()
    assert (
        cmd_resolve_context(
            project_root,
            cycle_id,
            stage,
            constraints_path=_holder_constraints(stage),
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    role = payload["domain_constraints"]["role"]
    assert role["persona"] == "product_thinker"
    assert role["instruction"]
    assert payload["after_dc"]["next_steps"] == ["product-spec"]


def test_load_constraints_config_from_explicit_path() -> None:
    from dx_domain_constraints_schema import load_constraints_config

    product = load_constraints_config(_holder_constraints("product-diagnostic"))
    tech = load_constraints_config(_holder_constraints("tech-diagnostic"))
    assert "impact_surface" in product["x_dimensions"]
    assert "impact_surface" in tech["x_dimensions"]
    assert product["stage"] == "product-diagnostic"
    assert tech["stage"] == "tech-diagnostic"
    assert product["cache_subdir"] == "product/diagnostic"
    assert tech["cache_subdir"] == "tech/diagnostic"
    assert product["role"]["persona"] == "product_thinker"
    assert tech["role"]["persona"] == "technical_decision_maker"
    assert tech.get("context_loading", {}).get("sources")


def test_session_cache_subdir_from_constraints_path(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dx_session_paths import session_cache_subdir
    from dx_workflow_common import CACHE_DIR

    monkeypatch.chdir(template_config)
    subdir = session_cache_subdir(
        template_config,
        "cycle-x",
        "product-diagnostic",
        CACHE_DIR,
        constraints_path=_holder_constraints("product-diagnostic"),
    )
    assert subdir == "product/diagnostic"
