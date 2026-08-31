#!/usr/bin/env python3
"""Tests for tech_arch_eval_adapter.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS_ROOT.parents[1]
_EVAL_SHELL = _SCRIPTS_ROOT / "eval"
_EVAL_SCRIPTS = _WORKFLOW_ROOT / "eval" / "scripts"
_KERNEL_CORE = _WORKFLOW_ROOT / "compose" / "scripts" / "eval"
_KERNEL_TESTS = _WORKFLOW_ROOT / "compose" / "scripts" / "tests"
for p in (_EVAL_SHELL, _EVAL_SCRIPTS, _KERNEL_CORE, _KERNEL_TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from eval_path import ensure_eval_script_layers  # noqa: E402

ensure_eval_script_layers()

import bootstrap  # noqa: F401
from compose_eval_adapter import ComposeEvalAdapter  # noqa: E402
from corpus_composition import is_composed_corpus_ref  # noqa: E402
from tech_arch_eval_adapter import (  # noqa: E402
    LULU_ARCH_COMPOSED_CORPUS_REF,
)
from tech_arch_eval_contributor import TechArchEvalContributor  # noqa: E402
from tech_arch_eval_policy import select_dimension_ids  # noqa: E402
from workflow_state_schema import init_compose_session  # noqa: E402
from init_working_helpers import seed_resolved_refs_for_eval  # noqa: E402

_COMMON_IDS = ["intent-fidelity", "parent-continuity", "norm-conformance"]

_CYCLE = "topic-arch-adapter"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _adapter() -> ComposeEvalAdapter:
    return ComposeEvalAdapter(
        workflow_id="lulu-arch",
        contributor=TechArchEvalContributor(),
    )


def _seed_session(tmp_path: Path) -> Path:
    from workflow_paths import seed_profile_pointer_for_tests  # noqa: WPS433

    base = tmp_path / _CACHE / _CYCLE / "lulu-arch"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, "lulu-arch")
    rev = base / "revision1"
    rev.mkdir(parents=True)
    (rev / "arch-doc.md").write_text("# arch\n", encoding="utf-8")
    return rev / "workflow-state.md"


class TestTechArchEvalAdapter:
    def test_registry_loads_lulu_arch(self) -> None:
        adapter = _adapter()
        assert adapter.corpus_ref_for_mode("tech") == LULU_ARCH_COMPOSED_CORPUS_REF
        assert is_composed_corpus_ref(LULU_ARCH_COMPOSED_CORPUS_REF)

    def test_resolve_eval_corpus_topic_mode(self, tmp_path: Path) -> None:
        ws = _seed_session(tmp_path)
        init_compose_session(ws, mode="tech")
        seed_resolved_refs_for_eval(ws, cycle_id=_CYCLE, stage="lulu-arch", mode="tech")
        adapter = _adapter()
        corpus = adapter.resolve_eval_corpus(_CYCLE, tmp_path)
        ids = _COMMON_IDS + select_dimension_ids()
        assert [d["id"] for d in corpus["dimensions"]] == ids
        assert corpus["scope"] == "lulu-arch"
        assert corpus["dimensions"][0]["review"]["output_path"] == "arch-review-e{M}1.md"

    def test_resolve_eval_corpus_rejects_feature_cycle(self, tmp_path: Path) -> None:
        ws = _seed_session(tmp_path)
        init_compose_session(ws, mode="tech")
        adapter = _adapter()
        with pytest.raises(ValueError, match="feature cycles do not evaluate"):
            adapter.resolve_eval_corpus("feat-arch-adapter", tmp_path)
