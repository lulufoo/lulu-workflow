#!/usr/bin/env python3
"""Tests for tech_design_draft_control.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_DRAFTING = _SCRIPTS_ROOT / "drafting"
_KERNEL_TESTS = _SCRIPTS_ROOT.parents[1] / "compose-kernel" / "scripts" / "tests"
_KERNEL_SECTION = _SCRIPTS_ROOT.parents[1] / "compose-kernel" / "scripts" / "section"
if str(_KERNEL_TESTS) not in sys.path:
    sys.path.insert(0, str(_KERNEL_TESTS))
if str(_KERNEL_SECTION) not in sys.path:
    sys.path.insert(0, str(_KERNEL_SECTION))
if str(_DRAFTING) not in sys.path:
    sys.path.insert(0, str(_DRAFTING))
import bootstrap  # noqa: F401, E402
from tech_design_draft_control import (  # noqa: E402
    advance_round,
    advance_to_freeedit,
    begin_inductive,
    begin_init,
    begin_round,
    draft_status,
    inductive_complete,
    init_complete,
)
from test_template_data import seed_template_cache  # noqa: E402

_CYCLE = "feat-design-init"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")
_DESIGN_ORDER = ["CTX", "GO", "SC", "NG", "I", "ST", "KD", "IF", "OQ", "VD", "OD"]


def _seed_design_registry(
    tmp_path: Path,
    *,
    section_order: list[str] | None = None,
) -> None:
    order = section_order or _DESIGN_ORDER
    sections = {
        key: {
            "heading": key,
            "aliases": [key.lower()],
            "upstream": [],
            "relations": {},
            "desc": f"Section {key}.",
        }
        for key in order
    }
    seed_template_cache(
        tmp_path,
        "tech-design",
        "tdt_section_registry_url",
        {
            "version": "1",
            "section_order": order,
            "document_preamble": "# Design\n",
            "sections": sections,
        },
    )
    import section_registry_schema  # noqa: WPS433

    section_registry_schema._registry_for_path.cache_clear()


def _minimal_design_doc() -> str:
    blocks = []
    for key in _DESIGN_ORDER:
        blocks.append(f"### {key} section title <!-- section-key:{key} -->\n\nBody for {key}.")
    return "# Design\n\n" + "\n\n".join(blocks) + "\n"


def _seed_init_artifacts(revision: Path, section_keys: list[str]) -> None:
    from init_compose_validation import write_minimal_init_work_artifacts  # noqa: WPS433

    write_minimal_init_work_artifacts(revision, section_keys)


def _seed_session(tmp_path: Path) -> Path:
    base = tmp_path / _CACHE / _CYCLE / "tech" / "design" / "revision1"
    base.mkdir(parents=True)
    session = base.parent.parent / "session-state.md"
    session.parent.mkdir(parents=True, exist_ok=True)
    session.write_text("---\nversion: 1\nactive_doc: 1\n---\n", encoding="utf-8")
    (base / "design-doc.md").write_text(_minimal_design_doc(), encoding="utf-8")
    diag = tmp_path / _CACHE / _CYCLE / "tech" / "diagnostic"
    diag.mkdir(parents=True)
    decision = diag / "decision-doc.md"
    decision.write_text("# Decision\n", encoding="utf-8")
    from delivered_refs_schema import DeliveredRef  # noqa: WPS433
    from init_drafting_helpers import tech_design_scope_refs  # noqa: WPS433
    from workflow_state_schema import init_drafting  # noqa: WPS433

    refs = [DeliveredRef(type="tech-diagnostic", path=str(decision.resolve()))]
    init_drafting(
        base / "workflow-state.md",
        mode="tech",
        delivered_refs=refs,
        scope_refs=tech_design_scope_refs(refs),
    )
    from workflow_paths import seed_profile_pointer_for_tests  # noqa: WPS433

    seed_profile_pointer_for_tests(tmp_path, _CYCLE, "tech-design")
    _seed_init_artifacts(base, _DESIGN_ORDER)
    return base


def _ready_session(tmp_path: Path) -> Path:
    _seed_design_registry(tmp_path)
    revision = _seed_session(tmp_path)
    init_complete(_CYCLE, tmp_path)
    return revision


def _inductive_dir(tmp_path: Path) -> Path:
    return tmp_path / _CACHE / _CYCLE / "tech" / "design" / "inductive-scope"


def _inductive_out_dir(tmp_path: Path) -> Path:
    return tmp_path / _CACHE / _CYCLE / "tech" / "design"


def _write_g4_closed_gate_state(tmp_path: Path) -> None:
    """Write a minimal inductive-gate-state.json with G4 closed."""
    import json

    out_dir = _inductive_out_dir(tmp_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    gate_state = {
        "version": "1",
        "cycle_id": _CYCLE,
        "stage": "tech-design",
        "active_gate": "G4",
        "gates": {
            "G1": {"status": "closed", "closed_at": "2026-01-01T00:00:00+00:00", "payload": None},
            "G2": {"status": "closed", "closed_at": "2026-01-01T00:00:00+00:00", "payload": None},
            "G3": {"status": "closed", "closed_at": "2026-01-01T00:00:00+00:00", "payload": None},
            "G4": {"status": "closed", "closed_at": "2026-01-01T00:00:00+00:00", "payload": None},
        },
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    (out_dir / "inductive-gate-state.json").write_text(
        json.dumps(gate_state, indent=2), encoding="utf-8"
    )


class TestTechDesignInductive:
    def test_begin_inductive_persists_state_and_dispatch(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        result = begin_inductive(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert "COMPOSE_PROFILE:      tech-design" in result["dispatch_input"]
        assert "SCOPE_DOC:" in result["dispatch_input"]
        assert "INDUCTIVE_OUT_DIR:" in result["dispatch_input"]
        progress = (revision / "drafting-progress.md").read_text(encoding="utf-8")
        assert "current_step: Inductive" in progress

    def test_begin_init_requires_inductive_first(self, tmp_path: Path):
        _seed_session(tmp_path)
        result = begin_init(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "Inductive" in result["reason"]

    def test_inductive_complete_requires_g4_closed(self, tmp_path: Path):
        _seed_session(tmp_path)
        begin_inductive(_CYCLE, tmp_path)

        # Case 1: no gate state at all -> fail
        missing = inductive_complete(_CYCLE, tmp_path)
        assert missing["ok"] is False
        assert "Gate 4" in missing["reason"]

        # Case 2: section files exist but G4 not closed -> still fail
        ind = _inductive_dir(tmp_path)
        ind.mkdir(parents=True, exist_ok=True)
        (ind / "ST.md").write_text("<!-- section-key:ST -->\n", encoding="utf-8")
        still_missing = inductive_complete(_CYCLE, tmp_path)
        assert still_missing["ok"] is False
        assert "Gate 4" in still_missing["reason"]

        # Case 3: G4 closed -> succeed (section_files list from disk)
        _write_g4_closed_gate_state(tmp_path)
        ok = inductive_complete(_CYCLE, tmp_path)
        assert ok["ok"] is True
        assert "ST.md" in ok["section_files"]

    def test_begin_init_after_inductive_includes_inductive_dir(self, tmp_path: Path):
        _seed_session(tmp_path)
        begin_inductive(_CYCLE, tmp_path)
        ind = _inductive_dir(tmp_path)
        ind.mkdir(parents=True, exist_ok=True)
        (ind / "ST.md").write_text("<!-- section-key:ST -->\n", encoding="utf-8")
        # G4 not closed -> begin_init must fail
        blocked = begin_init(_CYCLE, tmp_path)
        assert blocked["ok"] is False
        assert "Gate 4" in blocked["reason"]
        # G4 closed -> begin_init succeeds and includes INDUCTIVE_DIR
        _write_g4_closed_gate_state(tmp_path)
        result = begin_init(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert "INDUCTIVE_DIR:" in result["dispatch_input"]


class TestTechDesignDraftControl:
    def test_begin_init_dispatch_includes_profile(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        begin_inductive(_CYCLE, tmp_path)
        _write_g4_closed_gate_state(tmp_path)
        result = begin_init(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert "COMPOSE_PROFILE:      tech-design" in result["dispatch_input"]
        assert "OUTPUT_DOC_PATH:" in result["dispatch_input"]
        assert revision.as_posix() in result["dispatch_input"]

    def test_init_complete_validates_design_doc(self, tmp_path: Path):
        _seed_design_registry(tmp_path)
        _seed_session(tmp_path)
        result = init_complete(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "Initialized"
        assert "design-doc.md" in result["design_doc"]

    def test_init_complete_rejects_empty_section(self, tmp_path: Path):
        _seed_design_registry(tmp_path, section_order=["CTX", "GO"])
        revision = _seed_session(tmp_path)
        _seed_init_artifacts(revision, ["CTX", "GO"])
        (revision / "design-doc.md").write_text(
            "### CTX title <!-- section-key:CTX -->\n\n"
            "### GO title <!-- section-key:GO -->\n\nHas body\n",
            encoding="utf-8",
        )
        result = init_complete(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "empty body" in result["reason"]


class TestTechDesignDeprecatedRound:
    def test_begin_round_returns_failure(self, tmp_path: Path):
        _ready_session(tmp_path)
        result = begin_round(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "removed" in result["reason"]

    def test_advance_round_returns_failure(self, tmp_path: Path):
        _ready_session(tmp_path)
        result = advance_round(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "removed" in result["reason"]


class TestTechDesignAdvanceToFreeedit:
    def test_transitions_initialized_to_freeedit(self, tmp_path: Path):
        revision = _ready_session(tmp_path)
        result = advance_to_freeedit(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "FreeEdit"
        progress = (revision / "drafting-progress.md").read_text(encoding="utf-8")
        assert "current_step: FreeEdit" in progress

    def test_fails_without_init_complete(self, tmp_path: Path):
        _seed_session(tmp_path)
        result = advance_to_freeedit(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "init-complete" in result["reason"]

    def test_idempotent_when_already_freeedit(self, tmp_path: Path):
        _ready_session(tmp_path)
        advance_to_freeedit(_CYCLE, tmp_path)
        result = advance_to_freeedit(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "FreeEdit"


class TestTechDesignDraftStatus:
    def test_returns_step_after_init_complete(self, tmp_path: Path):
        _ready_session(tmp_path)
        result = draft_status(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "Initialized"
        assert result["cycle_id"] == _CYCLE
