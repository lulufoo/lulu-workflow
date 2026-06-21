#!/usr/bin/env python3
"""Tests for product_spec_draft_control.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_DRAFTING = _SCRIPTS_ROOT / "drafting"
_KERNEL_TESTS = _SCRIPTS_ROOT.parents[1] / "compose-kernel" / "scripts" / "tests"
if str(_KERNEL_TESTS) not in sys.path:
    sys.path.insert(0, str(_KERNEL_TESTS))
if str(_DRAFTING) not in sys.path:
    sys.path.insert(0, str(_DRAFTING))
import bootstrap  # noqa: F401, E402
from product_spec_draft_control import (  # noqa: E402
    advance_round,
    advance_to_freeedit,
    begin_init,
    begin_round,
    draft_status,
    init_complete,
)
from test_template_data import seed_template_cache  # noqa: E402

_CYCLE = "feat-product-spec-init"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")
_SECTION_ORDER = ["PB", "RN", "GO", "UR", "SN", "SC", "IO", "FL", "NG", "AC"]


def _seed_product_registry(tmp_path: Path, *, section_order: list[str] | None = None) -> None:
    order = section_order or _SECTION_ORDER
    sections = {
        key: {
            "heading": key,
            "aliases": [key.lower()],
            "upstream": [],
            "relations": {},
            "intent": f"Section {key}.",
        }
        for key in order
    }
    seed_template_cache(
        tmp_path,
        "product-spec",
        "pst_section_registry_url",
        {
            "version": "1",
            "section_order": order,
            "document_preamble": "# Product\n",
            "sections": sections,
        },
    )
    import section_registry_schema  # noqa: WPS433

    section_registry_schema._registry_for_path.cache_clear()


def _minimal_product_doc(*, section_order: list[str] | None = None) -> str:
    order = section_order or _SECTION_ORDER
    blocks = []
    for key in order:
        blocks.append(f"<!-- section-key:{key} -->\nBody for {key}.")
    return "# Product\n\n" + "\n\n".join(blocks) + "\n"


def _seed_session(tmp_path: Path) -> Path:
    base = tmp_path / _CACHE / _CYCLE / "product" / "spec" / "revision1"
    base.mkdir(parents=True)
    session = base.parent.parent / "session-state.md"
    session.parent.mkdir(parents=True, exist_ok=True)
    session.write_text("---\nversion: 1\nactive_doc: 1\n---\n", encoding="utf-8")
    (base / "product-doc.md").write_text(_minimal_product_doc(), encoding="utf-8")
    diag = tmp_path / _CACHE / _CYCLE / "product" / "diagnostic"
    diag.mkdir(parents=True)
    decision = diag / "decision-doc.md"
    decision.write_text("# Decision\n", encoding="utf-8")
    from delivered_refs_schema import DeliveredRef  # noqa: WPS433
    from workflow_state_schema import init_drafting  # noqa: WPS433

    init_drafting(
        base / "workflow-state.md",
        mode="product",
        delivered_refs=[
            DeliveredRef(type="product-diagnostic", path=str(decision.resolve())),
        ],
    )
    return base


def _ready_session(tmp_path: Path) -> Path:
    _seed_product_registry(tmp_path)
    revision = _seed_session(tmp_path)
    init_complete(_CYCLE, tmp_path)
    return revision


class TestProductSpecDraftControl:
    def test_begin_init_dispatch_includes_profile(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        result = begin_init(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert "COMPOSE_PROFILE:      product-spec" in result["dispatch_input"]
        assert "OUTPUT_DOC_PATH:" in result["dispatch_input"]
        assert revision.as_posix() in result["dispatch_input"]

    def test_init_complete_validates_product_doc(self, tmp_path: Path):
        _seed_product_registry(tmp_path)
        _seed_session(tmp_path)
        result = init_complete(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "Ready"
        assert "product-doc.md" in result["product_doc"]

    def test_init_complete_rejects_empty_section(self, tmp_path: Path):
        _seed_product_registry(tmp_path, section_order=["PB", "GO"])
        revision = _seed_session(tmp_path)
        (revision / "product-doc.md").write_text(
            "<!-- section-key:PB -->\n\n<!-- section-key:GO -->\nHas body\n",
            encoding="utf-8",
        )
        result = init_complete(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "empty body" in result["reason"]


class TestProductSpecBeginRound:
    def test_transitions_ready_to_round_iteration(self, tmp_path: Path):
        revision = _ready_session(tmp_path)
        result = begin_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "RoundIteration"
        assert result["round"] == 1
        progress = (revision / "drafting-progress.md").read_text(encoding="utf-8")
        assert "current_step: RoundIteration" in progress
        assert "round: 1" in progress
        assert (revision / "round-1" / "section-pointer.json").exists()

    def test_idempotent_when_already_round_iteration(self, tmp_path: Path):
        _ready_session(tmp_path)
        begin_round(_CYCLE, tmp_path)
        result = begin_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["round"] == 1

    def test_fails_without_progress(self, tmp_path: Path):
        _seed_session(tmp_path)
        result = begin_round(_CYCLE, tmp_path)
        assert result["ok"] is False


class TestProductSpecAdvanceRound:
    def test_increments_round(self, tmp_path: Path):
        revision = _ready_session(tmp_path)
        begin_round(_CYCLE, tmp_path)
        result = advance_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["round"] == 2
        progress = (revision / "drafting-progress.md").read_text(encoding="utf-8")
        assert "round: 2" in progress


class TestProductSpecAdvanceToFreeedit:
    def test_transitions_to_freeedit(self, tmp_path: Path):
        revision = _ready_session(tmp_path)
        begin_round(_CYCLE, tmp_path)
        result = advance_to_freeedit(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "FreeEdit"
        progress = (revision / "drafting-progress.md").read_text(encoding="utf-8")
        assert "current_step: FreeEdit" in progress

    def test_idempotent_when_already_freeedit(self, tmp_path: Path):
        _ready_session(tmp_path)
        begin_round(_CYCLE, tmp_path)
        advance_to_freeedit(_CYCLE, tmp_path)
        result = advance_to_freeedit(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "FreeEdit"


class TestProductSpecDraftStatus:
    def test_returns_round_and_step(self, tmp_path: Path):
        _ready_session(tmp_path)
        begin_round(_CYCLE, tmp_path)
        result = draft_status(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "RoundIteration"
        assert result["round"] == 1
        assert result["cycle_id"] == _CYCLE
