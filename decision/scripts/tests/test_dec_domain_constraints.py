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

from dec_decision_doc_schema import load_decision_doc  # noqa: E402
from dec_domain_constraints_schema import load_domain_constraints  # noqa: E402
from dec_gate_control import cmd_gate_close, cmd_init_session, cmd_resolve_context  # noqa: E402
from dec_register_control import cmd_register_append, cmd_register_update  # noqa: E402
from dec_workflow_common import decision_doc_path, domain_constraints_path  # noqa: E402
from dec_test_helpers import load_rendered_doc  # noqa: E402
from test_dec_gate_loop_a import _close_qe, _full_template  # noqa: E402


@pytest.fixture
def template_config(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / "skill-config" / "lulu-dev-workflow"
    cfg_dir.mkdir(parents=True)
    local_template = tmp_path / "decision-doc.template.md"
    local_template.write_text(_full_template(), encoding="utf-8")
    cfg_path = cfg_dir / "workflow-config.json"
    cfg_path.write_text(
        json.dumps({"decision": {"decision_doc_template_url": local_template.as_uri()}}),
        encoding="utf-8",
    )
    return tmp_path


_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]


def _holder_constraints(stage: str) -> Path:
    return _WORKFLOW_ROOT / stage / "constraints-feature.json"


def test_init_strips_omitted_sections(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-domain-001"
    stage = "decision"
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

    assert not (project_root / decision_doc_path(cycle_id, stage)).exists()

    doc = load_rendered_doc(project_root, cycle_id, stage)
    assert "## 5. Scope" not in doc
    assert "## 7. Execution Analysis" not in doc
    assert "## 4. Decision Rationale" in doc

    constraints = load_domain_constraints(project_root / domain_constraints_path(cycle_id, stage))
    assert "scope" in constraints["omitted_sections"]


def test_x_gate_close_respects_x_dimensions(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-domain-002"
    stage = "decision"
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

    assert not (project_root / decision_doc_path(cycle_id, stage)).exists()

    doc = load_rendered_doc(project_root, cycle_id, stage)
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
    stage = "decision"
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

    assert not (project_root / decision_doc_path(cycle_id, stage)).exists()

    doc = load_rendered_doc(project_root, cycle_id, stage)
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
    stage = "decision"
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
    stage = "lulu-bet"
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
    constraints = payload["domain_constraints"]
    assert constraints["objective"]
    assert constraints["domain"]["name"] == "product"
    assert constraints["domain"]["instruction"]
    assert len(constraints["domain"]["dimension_framing"]) == 5
    assert payload["after_dc"]["next_steps"] == ["lulu-spec"]


def test_load_constraints_config_from_explicit_path() -> None:
    from dec_domain_constraints_schema import ALL_X_DIMENSIONS, load_constraints_config

    product = load_constraints_config(_holder_constraints("lulu-bet"))
    tech = load_constraints_config(_holder_constraints("lulu-approach"))
    assert "impact_surface" in product["x_dimensions"]
    assert "impact_surface" in tech["x_dimensions"]
    assert product["stage"] == "lulu-bet"
    assert tech["stage"] == "lulu-approach"
    assert product["cache_subdir"] == "lulu-bet"
    assert tech["cache_subdir"] == "lulu-approach"
    assert product["role"]["persona"] == "product_thinker"
    assert tech["role"]["persona"] == "technical_decision_maker"
    # constraints-*.json templates only ever carry an empty placeholder —
    # context.sources is 100% auto-derived at runtime by resolve_context.py
    # (scripts/context_loading.py), never declared here.
    assert product["context"] == {"sources": []}
    assert tech["context"] == {"sources": []}
    for holder in (product, tech):
        assert holder["objective"]
        assert holder["domain"]["name"]
        assert holder["domain"]["instruction"]
        assert set(holder["domain"]["dimension_framing"]) == set(ALL_X_DIMENSIONS)


def test_holder_constraints_require_objective_and_domain() -> None:
    from dec_domain_constraints_schema import load_constraints_config

    base = json.loads(_holder_constraints("lulu-bet").read_text(encoding="utf-8"))
    missing_objective = {k: v for k, v in base.items() if k != "objective"}
    with pytest.raises(ValueError, match="objective is required"):
        load_constraints_config_from_dict(missing_objective, stage="lulu-bet")

    missing_domain_instruction = json.loads(
        _holder_constraints("lulu-bet").read_text(encoding="utf-8")
    )
    missing_domain_instruction["domain"] = {
        "name": "product",
        "instruction": "",
        "dimension_framing": missing_domain_instruction["domain"]["dimension_framing"],
    }
    with pytest.raises(ValueError, match="domain.instruction is required"):
        load_constraints_config_from_dict(missing_domain_instruction, stage="lulu-bet")


def load_constraints_config_from_dict(data: dict, *, stage: str) -> dict:
    import tempfile

    from dec_domain_constraints_schema import load_constraints_config

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(data, handle)
        path = Path(handle.name)
    try:
        return load_constraints_config(path, stage=stage)
    finally:
        path.unlink(missing_ok=True)


def test_session_cache_subdir_from_constraints_path(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dec_session_paths import session_cache_subdir
    from dec_workflow_common import CACHE_DIR

    monkeypatch.chdir(template_config)
    subdir = session_cache_subdir(
        template_config,
        "cycle-x",
        "lulu-bet",
        CACHE_DIR,
        constraints_path=_holder_constraints("lulu-bet"),
    )
    assert subdir == "lulu-bet"


def test_merge_domain_constraints_context_replaces_whole_block() -> None:
    """The override's context fully replaces the base one — a holder's
    resolver script hands in an already-resolved block, and
    merge_domain_constraints must not attempt to deep-merge it field by
    field (the base template only ever carries an empty sources placeholder,
    so a field merge would just be a no-op passthrough instead of the
    freshly resolved payload)."""
    from dec_domain_constraints_schema import load_constraints_config, merge_domain_constraints

    base = load_constraints_config(_holder_constraints("lulu-approach"))
    assert base["context"] == {"sources": []}

    override = {
        "context": {
            "sources": [
                {
                    "kind": "topic",
                    "loaded_message": "topic ctx",
                    "status": "loaded",
                    "resolved_doc_path": "/cache/topic-line/lulu-arch/revision1/lulu-arch-doc.md",
                },
            ],
        },
    }
    merged = merge_domain_constraints(base, override)
    assert merged["context"] == {
        "sources": [
            {
                "kind": "topic",
                "loaded_message": "topic ctx",
                "status": "loaded",
                "resolved_doc_path": "/cache/topic-line/lulu-arch/revision1/lulu-arch-doc.md",
            },
        ],
    }


def test_merge_domain_constraints_context_skipped_status_passes_through() -> None:
    from dec_domain_constraints_schema import load_constraints_config, merge_domain_constraints

    base = load_constraints_config(_holder_constraints("lulu-bet"))
    merged = merge_domain_constraints(base, {"context": {"status": "skipped"}})
    assert merged["context"] == {"status": "skipped"}


def test_merge_domain_constraints_without_context_override_keeps_base() -> None:
    from dec_domain_constraints_schema import load_constraints_config, merge_domain_constraints

    base = load_constraints_config(_holder_constraints("lulu-approach"))
    merged = merge_domain_constraints(base, {"omitted_sections": ["scope"]})
    assert merged["context"] == base["context"]
