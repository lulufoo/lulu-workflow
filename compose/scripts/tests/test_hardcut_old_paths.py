#!/usr/bin/env python3
"""Hard-cut: retired DAG / pointer / progress / CLI modules must stay gone."""

from __future__ import annotations

from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _WORKFLOW_ROOT / "compose"
_ENGINE = _COMPOSE / "SKILL.md"
_INNER = _COMPOSE / "references" / "l-execution.md"
_EVAL = _WORKFLOW_ROOT / "eval" / "SKILL.md"

_DELETED_MODULES = (
    "compose/scripts/schema/session/discussion_pointer_schema.py",
    "compose/scripts/core/discussion_pointer_control.py",
    "compose/scripts/schema/session/dependency_tree_schema.py",
    "compose/scripts/schema/session/slice_rulers_schema.py",
    "compose/scripts/schema/session/l_step_progress_schema.py",
    "compose/scripts/core/multi_slice_control.py",
    "compose/scripts/core/session_evaluating.py",
    "compose/scripts/core/start_adapter.py",
    "compose/scripts/schema/session/split_intake_schema.py",
    "compose/scripts/section/chapters_control.py",
    "compose/scripts/inductive/inductive_facts_projection.py",
    "compose/scripts/core/init.py",
    "compose/scripts/section/_title_map_io.py",
    "compose/scripts/inductive/inductive_subagent_guard.py",
    "compose/scripts/section/display_layer_gates.py",
    "compose/scripts/inductive/kw_facets.py",
    "compose/scripts/writing/writing_compose_validation.py",
    "compose/scripts/templates/load_compose_template.py",
    "compose/scripts/session/holder_finalize.py",
)

_DELETED_DATA = (
    "compose/scripts/writing/form_structure_body_probes.json",
    "compose/scripts/section/form_structure_body_probes.json",
    "compose/templates/anchor-ledger.template.md",
)

_DELETED_TESTS = (
    "compose/scripts/tests/test_discussion_pointer_schema.py",
    "compose/scripts/tests/test_dependency_tree_schema.py",
    "compose/scripts/tests/test_kernel_l_step_control.py",
    "compose/scripts/tests/test_kernel_l_step_progress_schema.py",
    "compose/scripts/tests/test_session_evaluating.py",
    "compose/scripts/tests/test_start_dynamic_adapter.py",
    "compose/scripts/tests/test_active_slice_dir.py",
    "compose/scripts/tests/test_multi_slice_control.py",
    "compose/scripts/tests/test_chapters_control.py",
    "compose/scripts/tests/test_inductive_facts_projection.py",
    "compose/scripts/tests/test_display_layer_gates.py",
    "compose/scripts/tests/test_writing_compose_validation.py",
    "compose/scripts/tests/test_load_compose_template.py",
)

_FORBIDDEN_SKILL_TOKENS = (
    "$MULTI_SLICE",
    "$L_SLICE",
    "$INDUCTIVE_FACTS_PROJ",
    "lock-tree",
    "begin-inductive",
    "begin-deductive",
    "assemble-package",
    "accept-l",
    "fix-l",
)


def test_deleted_production_modules_absent() -> None:
    for rel in _DELETED_MODULES:
        assert not (_WORKFLOW_ROOT / rel).exists(), rel


def test_deleted_data_files_absent() -> None:
    for rel in _DELETED_DATA:
        assert not (_WORKFLOW_ROOT / rel).exists(), rel


def test_deleted_test_modules_absent() -> None:
    for rel in _DELETED_TESTS:
        assert not (_WORKFLOW_ROOT / rel).exists(), rel


def test_engine_and_inner_drop_retired_cli() -> None:
    text = _ENGINE.read_text(encoding="utf-8") + "\n" + _INNER.read_text(encoding="utf-8")
    for token in _FORBIDDEN_SKILL_TOKENS:
        assert token not in text, token


def test_eval_skill_returns_choice_caller_owns_l_step() -> None:
    text = _EVAL.read_text(encoding="utf-8")
    assert "$L_SLICE" not in text
    assert "abandon-evaluation" not in text
    assert "$L_STEP" not in text
    inner = _INNER.read_text(encoding="utf-8")
    assert "$L_STEP accept --confirm" in inner
    assert "$L_STEP fix --confirm" in inner
    assert "Eval SKILL does not run `$L_STEP`" in inner
