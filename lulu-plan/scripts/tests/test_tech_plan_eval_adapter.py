#!/usr/bin/env python3
"""Tests for tech_plan_eval_adapter.py."""

import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS_ROOT.parents[1]
_EVAL_SHELL = _SCRIPTS_ROOT / "eval"
_EVAL_SCRIPTS = _WORKFLOW_ROOT / "eval" / "scripts"
_KERNEL_TESTS = _WORKFLOW_ROOT / "compose" / "scripts" / "tests"
for p in (_EVAL_SHELL, _EVAL_SCRIPTS, _KERNEL_TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import bootstrap  # noqa: F401
from tech_plan_eval_adapter import (  # noqa: E402
    LULU_PLAN_COMPOSED_CORPUS_REF,
    TechPlanEvalAdapter,
)
import sys
from pathlib import Path as _P
_COMPOSE_TESTS = _P(__file__).resolve().parents[3] / 'compose' / 'scripts' / 'tests'
if str(_COMPOSE_TESTS) not in sys.path:
    sys.path.insert(0, str(_COMPOSE_TESTS))
from init_drafting_helpers import init_drafting_ready  # noqa: E402
from init_drafting_helpers import seed_frozen_delivered  # noqa: E402

_CYCLE = "feat-adapter"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _seed_session(tmp_path: Path) -> Path:
    from workflow_paths import seed_profile_pointer_for_tests  # noqa: WPS433

    base = tmp_path / _CACHE / _CYCLE / "lulu-plan"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, "lulu-plan")
    return base / "revision1" / "workflow-state.md"


class TestTechPlanEvalAdapter:
    def test_corpus_ref_for_mode_is_composed(self):
        adapter = TechPlanEvalAdapter()
        assert adapter.corpus_ref_for_mode("product") == LULU_PLAN_COMPOSED_CORPUS_REF
        assert adapter.corpus_ref_for_mode("tech") == LULU_PLAN_COMPOSED_CORPUS_REF

    def test_resolve_eval_corpus_no_tech_upstream(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting_ready(ws, mode="tech")
        adapter = TechPlanEvalAdapter()
        corpus = adapter.resolve_eval_corpus(_CYCLE, tmp_path)
        assert [d["legacy_alias"] for d in corpus["dimensions"]] == ["e2", "e3"]

    def test_resolve_eval_corpus_tech_design_upstream_adds_tech_conformance(
        self, tmp_path: Path
    ):
        from delivered_refs_schema import DeliveredRef  # noqa: WPS433

        ws = _seed_session(tmp_path)
        design_doc = tmp_path / "design-doc.md"
        design_doc.write_text("# Design\n", encoding="utf-8")
        refs = [DeliveredRef(type="lulu-design", path=str(design_doc.resolve()))]
        init_drafting_ready(ws, mode="tech")
        seed_frozen_delivered(ws, refs)
        adapter = TechPlanEvalAdapter()
        corpus = adapter.resolve_eval_corpus(_CYCLE, tmp_path)
        ids = [d["id"] for d in corpus["dimensions"]]
        assert ids == ["codebase-consistency", "solution-quality", "tech-conformance"]

    def test_resolve_eval_corpus_tech_diagnostic_upstream_adds_tech_conformance(
        self, tmp_path: Path
    ):
        from delivered_refs_schema import DeliveredRef  # noqa: WPS433

        ws = _seed_session(tmp_path)
        decision_doc = tmp_path / "decision-doc.md"
        decision_doc.write_text("# Decision\n", encoding="utf-8")
        refs = [DeliveredRef(type="lulu-approach", path=str(decision_doc.resolve()))]
        init_drafting_ready(ws, mode="tech")
        seed_frozen_delivered(ws, refs)
        adapter = TechPlanEvalAdapter()
        corpus = adapter.resolve_eval_corpus(_CYCLE, tmp_path)
        ids = [d["id"] for d in corpus["dimensions"]]
        assert ids == ["codebase-consistency", "solution-quality", "tech-conformance"]

    def test_resolve_evaluate_state_path(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting_ready(ws, mode="tech")
        adapter = TechPlanEvalAdapter()
        es_path = adapter.resolve_evaluate_state_path(_CYCLE, tmp_path)
        assert es_path.name == "evaluate-state.md"
        assert "revision1" in es_path.as_posix()

    def test_resolve_eval_corpus_topic_blocks(self, tmp_path: Path):
        from workflow_paths import seed_profile_pointer_for_tests  # noqa: WPS433

        cycle = "topic-eval-blocked"
        base = tmp_path / _CACHE / cycle / "lulu-plan"
        base.mkdir(parents=True)
        (base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\n---\n",
            encoding="utf-8",
        )
        seed_profile_pointer_for_tests(tmp_path, cycle, "lulu-plan")
        ws = base / "revision1" / "workflow-state.md"
        init_drafting_ready(ws, mode="tech")
        adapter = TechPlanEvalAdapter()
        with pytest.raises(ValueError, match="topic cycles do not evaluate in lulu-plan"):
            adapter.resolve_eval_corpus(cycle, tmp_path)

    def test_eval_control_main_rejects_direct_invocation(self):
        if str(_EVAL_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(_EVAL_SCRIPTS))
        from eval_control import main  # noqa: WPS433

        assert main() != 0
