#!/usr/bin/env python3
"""Tests for eval_control.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_control import dispatch_list, init_round  # noqa: E402
from evaluate_state_schema import load_evaluate_state  # noqa: E402
from workflow_state_schema import init_drafting  # noqa: E402

_CYCLE = "feat-eval-control"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _seed_session(tmp_path: Path, *, active_doc: int = 1) -> Path:
    base = tmp_path / _CACHE / _CYCLE / "tech" / "plan"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        f"---\nversion: 1\nactive_doc: {active_doc}\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    ws = base / f"revision{active_doc}" / "workflow-state.md"
    return ws


class TestDispatchList:
    def test_product_mode(self):
        assert dispatch_list("product") == ["e1", "e2", "e3"]

    def test_tech_mode(self):
        assert dispatch_list("tech") == ["e2", "e3"]

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="invalid mode"):
            dispatch_list("invalid")


class TestInitRound:
    def test_product_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")

        result = init_round(_CYCLE, tmp_path, mode="product")

        assert result["ok"] is True
        assert result["command"] == "init-round"
        assert result["mode"] == "product"
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["phase"] == "evaluate"
        assert es["current_dimension"] == "e1"
        assert es["e1_status"] == "pending"
        assert es["e2_status"] == "pending"
        assert es["e3_status"] == "pending"

    def test_tech_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")

        result = init_round(_CYCLE, tmp_path, mode="tech")

        assert result["ok"] is True
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["current_dimension"] == "e2"
        assert es["e1_status"] == "complete"
        assert es["e2_status"] == "pending"
        assert es["e3_status"] == "pending"

    def test_invalid_mode_raises(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")

        with pytest.raises(ValueError, match="invalid mode"):
            init_round(_CYCLE, tmp_path, mode="invalid")
