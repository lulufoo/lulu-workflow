#!/usr/bin/env python3
"""Tests for product_spec_eval_adapter.py."""

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
from product_spec_eval_adapter import (  # noqa: E402
    PRODUCT_SPEC_COMPOSED_CORPUS_REF,
    ProductSpecEvalAdapter,
)
from corpus_compose import corpus_fingerprint  # noqa: E402
from delivered_refs_schema import DeliveredRef  # noqa: E402
from product_spec_eval_policy import select_dimension_ids  # noqa: E402
from workflow_state_schema import init_drafting  # noqa: E402
from init_drafting_helpers import seed_delivered_refs_file, seed_provenance_artifacts  # noqa: E402

_CYCLE = "feat-lulu-spec-adapter"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _seed_session(tmp_path: Path) -> Path:
    from workflow_paths import seed_profile_pointer_for_tests  # noqa: WPS433

    base = tmp_path / _CACHE / _CYCLE / "lulu-spec"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    rev = base / "revision1"
    rev.mkdir(parents=True)
    (rev / "product-doc.md").write_text("# product\n", encoding="utf-8")
    diag = tmp_path / _CACHE / _CYCLE / "lulu-bet" / "decision-doc.md"
    diag.parent.mkdir(parents=True, exist_ok=True)
    diag.write_text("# decision\n", encoding="utf-8")
    ws = rev / "workflow-state.md"
    refs = [DeliveredRef(type="lulu-bet", path=str(diag.resolve()))]
    seed_delivered_refs_file(tmp_path, _CYCLE, refs)
    init_drafting(ws, mode="product")
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, "lulu-spec")
    seed_provenance_artifacts(
        ws,
        cycle_id=_CYCLE,
        project_root=tmp_path,
        stage="lulu-spec",
        mode="product",
        scope_refs=refs,
    )
    return ws


class TestProductSpecEvalAdapter:
    def test_registry_loads_product_spec(self):
        adapter = ProductSpecEvalAdapter()
        assert adapter.corpus_ref_for_mode("product") == PRODUCT_SPEC_COMPOSED_CORPUS_REF

    def test_resolve_eval_corpus(self, tmp_path: Path):
        _seed_session(tmp_path)
        adapter = ProductSpecEvalAdapter()
        corpus = adapter.resolve_eval_corpus(_CYCLE, tmp_path)
        ids = select_dimension_ids()
        assert [d["id"] for d in corpus["dimensions"]] == ids
        assert corpus["scope"] == "lulu-spec"
        assert corpus["dimensions"][0]["review"]["output_path"] == "product-review-e{M}1.md"
        assert corpus_fingerprint(ids, cycle_type="feature")

    def test_eval_paths_compose_doc(self, tmp_path: Path):
        _seed_session(tmp_path)
        adapter = ProductSpecEvalAdapter()
        es_path = adapter.resolve_evaluate_state_path(_CYCLE, tmp_path)
        paths = adapter.eval_paths(
            _CYCLE,
            tmp_path,
            active_doc=1,
            evaluate_round=1,
            es_path=es_path,
        )
        assert paths["compose_doc"].endswith("/lulu-spec/revision1/product-doc.md")

    def test_corpus_bind_extensions_includes_decision_ref(self, tmp_path: Path):
        _seed_session(tmp_path)
        adapter = ProductSpecEvalAdapter()
        bind = adapter.corpus_bind_extensions(_CYCLE, tmp_path)
        assert bind["decision_ref"].endswith("/lulu-bet/decision-doc.md")
        assert "pst_product_eval_framework_url" in bind

    def test_resolve_evaluate_state_path(self, tmp_path: Path):
        _seed_session(tmp_path)
        adapter = ProductSpecEvalAdapter()
        es_path = adapter.resolve_evaluate_state_path(_CYCLE, tmp_path)
        assert es_path.name == "evaluate-state.md"
        assert "lulu-spec/revision1" in es_path.as_posix()

    def test_resolve_eval_corpus_topic_blocks(self, tmp_path: Path):
        cycle = "topic-lulu-spec-blocked"
        base = tmp_path / _CACHE / cycle / "lulu-spec"
        base.mkdir(parents=True)
        (base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\n---\n",
            encoding="utf-8",
        )
        ws = base / "revision1" / "workflow-state.md"
        ws.parent.mkdir(parents=True, exist_ok=True)
        init_drafting(ws, mode="product")
        adapter = ProductSpecEvalAdapter()
        with pytest.raises(ValueError, match="topic cycles do not evaluate in lulu-spec"):
            adapter.resolve_eval_corpus(cycle, tmp_path)
