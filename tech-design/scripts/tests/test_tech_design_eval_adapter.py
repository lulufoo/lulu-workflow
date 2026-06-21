#!/usr/bin/env python3
"""Tests for tech_design_eval_adapter.py."""

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
from workflow_adapter_loader import load_adapter  # noqa: E402
from corpus_compose import TECH_DESIGN_COMPOSED_CORPUS_REF, corpus_fingerprint  # noqa: E402
from tech_design_eval_policy import select_dimension_ids  # noqa: E402
from workflow_state_schema import init_drafting  # noqa: E402

_CYCLE = "feat-design-adapter"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _seed_session(tmp_path: Path) -> Path:
    base = tmp_path / _CACHE / _CYCLE / "tech" / "design"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    rev = base / "revision1"
    rev.mkdir(parents=True)
    (rev / "design-doc.md").write_text("# design\n", encoding="utf-8")
    return rev / "workflow-state.md"


class TestTechDesignEvalAdapter:
    def test_registry_loads_tech_design(self):
        adapter = load_adapter("tech-design")
        assert adapter.corpus_ref_for_mode("tech") == TECH_DESIGN_COMPOSED_CORPUS_REF

    def test_resolve_eval_corpus(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        adapter = load_adapter("tech-design")
        corpus = adapter.resolve_eval_corpus(_CYCLE, tmp_path)
        ids = select_dimension_ids()
        assert [d["id"] for d in corpus["dimensions"]] == ids
        assert corpus["scope"] == "tech-design"
        assert corpus["dimensions"][0]["review"]["output_path"] == "design-review-e{M}1.md"
        assert corpus_fingerprint(ids, cycle_type="feature")

    def test_eval_paths_compose_doc(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        adapter = load_adapter("tech-design")
        es_path = adapter.resolve_evaluate_state_path(_CYCLE, tmp_path)
        paths = adapter.eval_paths(
            _CYCLE,
            tmp_path,
            active_doc=1,
            evaluate_round=1,
            es_path=es_path,
        )
        assert paths["compose_doc"].endswith("/tech/design/revision1/design-doc.md")

    def test_session_context_product_ref(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        from init_drafting_helpers import product_delivered_refs  # noqa: WPS433

        init_drafting(ws, mode="product", delivered_refs=product_delivered_refs("/p.md"))
        adapter = load_adapter("tech-design")
        ctx = adapter.session_context(_CYCLE, tmp_path)
        assert ctx.product_ref == "/p.md"

    def test_resolve_evaluate_state_path(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        adapter = load_adapter("tech-design")
        es_path = adapter.resolve_evaluate_state_path(_CYCLE, tmp_path)
        assert es_path.name == "evaluate-state.md"
        assert "tech/design/revision1" in es_path.as_posix()

    def test_resolve_eval_corpus_topic_blocks(self, tmp_path: Path):
        cycle = "topic-design-blocked"
        base = tmp_path / _CACHE / cycle / "tech" / "design"
        base.mkdir(parents=True)
        (base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\n---\n",
            encoding="utf-8",
        )
        ws = base / "revision1" / "workflow-state.md"
        ws.parent.mkdir(parents=True, exist_ok=True)
        init_drafting(ws, mode="tech")
        adapter = load_adapter("tech-design")
        with pytest.raises(ValueError, match="topic cycles do not evaluate in tech-design"):
            adapter.resolve_eval_corpus(cycle, tmp_path)
