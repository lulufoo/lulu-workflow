#!/usr/bin/env python3
"""Tests for tech-plan eval_workflow_adapter."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval" / "scripts"))

from adapter_registry import load_adapter  # noqa: E402
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
    def test_load_via_registry(self):
        adapter = load_adapter("tech-plan")
        assert adapter.corpus_ref_for_mode("product") == "tech-plan-product@4"
        assert adapter.corpus_ref_for_mode("tech") == "tech-plan-tech@4"

    def test_resolve_evaluate_state_path(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")
        adapter = load_adapter("tech-plan")
        es_path = adapter.resolve_evaluate_state_path(_CYCLE, tmp_path)
        assert es_path.name == "evaluate-state.md"
        assert "revision1" in es_path.as_posix()

    def test_unknown_workflow_raises(self):
        with pytest.raises(ValueError, match="unknown workflow"):
            load_adapter("product-plan")
