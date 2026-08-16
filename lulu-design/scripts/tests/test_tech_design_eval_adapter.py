#!/usr/bin/env python3
"""Tests for tech_design_eval_adapter.py."""

import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS_ROOT.parents[1]
_EVAL_SHELL = _SCRIPTS_ROOT / "eval"
_EVAL_SCRIPTS = _WORKFLOW_ROOT / "eval" / "scripts"
_KERNEL_CORE = _WORKFLOW_ROOT / "compose" / "scripts" / "core"
_KERNEL_TESTS = _WORKFLOW_ROOT / "compose" / "scripts" / "tests"
for p in (_EVAL_SHELL, _EVAL_SCRIPTS, _KERNEL_CORE, _KERNEL_TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import bootstrap  # noqa: F401
from compose_eval_adapter import ComposeEvalAdapter  # noqa: E402
from tech_design_eval_adapter import (  # noqa: E402
    TECH_DESIGN_COMPOSED_CORPUS_REF,
)
from tech_design_eval_contributor import TechDesignEvalContributor  # noqa: E402
from corpus_compose import corpus_fingerprint  # noqa: E402
from tech_design_eval_policy import select_dimension_ids  # noqa: E402
from init_working_helpers import (  # noqa: E402
    init_working_ready,
    product_delivered_refs,
    seed_frozen_delivered,
    seed_resolved_refs_for_eval,
)

_COMMON_IDS = ["intent-fidelity", "parent-continuity", "norm-conformance"]

_CYCLE = "feat-design-adapter"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _adapter() -> ComposeEvalAdapter:
    return ComposeEvalAdapter(
        workflow_id="lulu-design",
        contributor=TechDesignEvalContributor(),
    )


def _seed_session(tmp_path: Path) -> Path:
    from workflow_paths import seed_profile_pointer_for_tests  # noqa: WPS433

    base = tmp_path / _CACHE / _CYCLE / "lulu-design"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, "lulu-design")
    rev = base / "revision1"
    rev.mkdir(parents=True)
    return rev / "workflow-state.md"


def _ready(ws: Path, *, mode: str) -> None:
    init_working_ready(ws, mode=mode)
    (ws.parent / "L1" / "design-doc.md").write_text("# design\n", encoding="utf-8")
    seed_resolved_refs_for_eval(ws, cycle_id=_CYCLE, stage="lulu-design", mode=mode)


class TestTechDesignEvalAdapter:
    def test_registry_loads_tech_design(self):
        adapter = _adapter()
        assert adapter.corpus_ref_for_mode("tech") == TECH_DESIGN_COMPOSED_CORPUS_REF

    def test_resolve_eval_corpus_tech_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        _ready(ws, mode="tech")

        adapter = _adapter()
        corpus = adapter.resolve_eval_corpus(_CYCLE, tmp_path)
        ids = _COMMON_IDS + select_dimension_ids()
        assert [d["id"] for d in corpus["dimensions"]] == ids
        assert corpus["scope"] == "lulu-design"
        assert corpus["dimensions"][0]["review"]["output_path"] == "design-review-e{M}1.md"
        assert corpus_fingerprint(ids, cycle_type="feature")

    def test_resolve_eval_corpus_product_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        _ready(ws, mode="product")
        seed_frozen_delivered(ws, product_delivered_refs("/p.md"))
        adapter = _adapter()
        corpus = adapter.resolve_eval_corpus(_CYCLE, tmp_path)
        assert [d["id"] for d in corpus["dimensions"]] == _COMMON_IDS + [
            "codebase-consistency",
            "solution-quality",
        ]
        assert corpus["dimensions"][2]["review"]["output_path"] == "design-review-e{M}3.md"

    def test_eval_paths_compose_doc(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        _ready(ws, mode="tech")
        adapter = _adapter()
        es_path = adapter.resolve_evaluate_state_path(_CYCLE, tmp_path)
        paths = adapter.eval_paths(
            _CYCLE,
            tmp_path,
            active_doc=1,
            evaluate_round=1,
            es_path=es_path,
        )
        assert paths["compose_doc"].endswith("/lulu-design/revision1/L1/design-doc.md")

    def test_session_context_upstream_baseline_ref(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        _ready(ws, mode="product")
        seed_frozen_delivered(ws, product_delivered_refs("/p.md"))
        adapter = _adapter()
        ctx = adapter.session_context(_CYCLE, tmp_path)
        assert ctx.upstream_baseline_ref == "/p.md"

    def test_resolve_evaluate_state_path(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        _ready(ws, mode="tech")
        adapter = _adapter()
        es_path = adapter.resolve_evaluate_state_path(_CYCLE, tmp_path)
        assert es_path.name == "evaluate-state.md"
        assert "lulu-design/revision1" in es_path.as_posix()

    def test_resolve_eval_corpus_topic_blocks(self, tmp_path: Path):
        from workflow_paths import seed_profile_pointer_for_tests  # noqa: WPS433

        cycle = "topic-design-blocked"
        base = tmp_path / _CACHE / cycle / "lulu-design"
        base.mkdir(parents=True)
        (base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\n---\n",
            encoding="utf-8",
        )
        seed_profile_pointer_for_tests(tmp_path, cycle, "lulu-design")
        ws = base / "revision1" / "workflow-state.md"
        ws.parent.mkdir(parents=True, exist_ok=True)
        _ready(ws, mode="tech")
        adapter = _adapter()
        with pytest.raises(ValueError, match="topic cycles do not evaluate in lulu-design"):
            adapter.resolve_eval_corpus(cycle, tmp_path)
