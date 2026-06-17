#!/usr/bin/env python3
"""Tests for tech_plan_eval_adapter.py."""

import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS_ROOT.parents[1]
_EVAL_SHELL = _SCRIPTS_ROOT / "eval"
_EVAL_SCRIPTS = _WORKFLOW_ROOT / "eval" / "scripts"
_KERNEL_TESTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts" / "tests"
for p in (_EVAL_SHELL, _EVAL_SCRIPTS, _KERNEL_TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import bootstrap  # noqa: F401
from adapter_registry import load_adapter  # noqa: E402
from corpus_compose import COMPOSED_CORPUS_REF, corpus_fingerprint  # noqa: E402
from tech_plan_eval_policy import select_dimension_ids  # noqa: E402
from workflow_state_schema import init_drafting  # noqa: E402

_CYCLE = "feat-adapter"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _seed_session(tmp_path: Path) -> Path:
    base = tmp_path / _CACHE / _CYCLE / "tech" / "plan"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    return base / "revision1" / "workflow-state.md"


class TestTechPlanEvalAdapter:
    def test_corpus_ref_for_mode_is_composed(self):
        adapter = load_adapter("tech-plan")
        assert adapter.corpus_ref_for_mode("product") == COMPOSED_CORPUS_REF
        assert adapter.corpus_ref_for_mode("tech") == COMPOSED_CORPUS_REF

    def test_resolve_eval_corpus_product_ref(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")
        adapter = load_adapter("tech-plan")
        corpus = adapter.resolve_eval_corpus(_CYCLE, tmp_path)
        ids = select_dimension_ids(
            product_ref="/p.md",
            mode="product",
        )
        assert [d["id"] for d in corpus["dimensions"]] == ids
        assert corpus_fingerprint(ids, cycle_type="feature")

    def test_resolve_eval_corpus_tech_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        adapter = load_adapter("tech-plan")
        corpus = adapter.resolve_eval_corpus(_CYCLE, tmp_path)
        assert [d["legacy_alias"] for d in corpus["dimensions"]] == ["e2", "e3"]

    def test_resolve_evaluate_state_path(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")
        adapter = load_adapter("tech-plan")
        es_path = adapter.resolve_evaluate_state_path(_CYCLE, tmp_path)
        assert es_path.name == "evaluate-state.md"
        assert "revision1" in es_path.as_posix()

    def test_resolve_eval_corpus_topic_blocks(self, tmp_path: Path):
        cycle = "topic-eval-blocked"
        base = tmp_path / _CACHE / cycle / "tech" / "plan"
        base.mkdir(parents=True)
        (base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\n---\n",
            encoding="utf-8",
        )
        ws = base / "revision1" / "workflow-state.md"
        init_drafting(ws, mode="tech")
        adapter = load_adapter("tech-plan")
        with pytest.raises(ValueError, match="topic eval stamps are not implemented"):
            adapter.resolve_eval_corpus(cycle, tmp_path)

    def test_unknown_workflow_raises(self):
        with pytest.raises(ValueError, match="unknown workflow"):
            load_adapter("product-plan")
