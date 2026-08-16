#!/usr/bin/env python3
"""Tests for Compose common Eval bind, skip, merge, and parent resolve."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import bootstrap  # noqa: F401

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
if str(_INDUCTIVE_DIR) not in sys.path:
    sys.path.insert(0, str(_INDUCTIVE_DIR))
from delivered_refs_schema import DeliveredRef
from resolved_refs_schema import (
    ResolvedRefsError,
    write_resolved_refs,
    strict_load_resolved_refs,
)
from compose_common_eval import (
    COMMON_DIMENSION_IDS,
    SKIP_EMPTY_INTENT,
    SKIP_EMPTY_NORM,
    ComposeCommonEvalError,
    compose_common_dimensions,
    merge_common_and_stage,
    resolve_parent_continuity_sot,
)
from inductive_gate_state_schema import (
    close_gate,
    init_gate_state,
    load_gate_state,
    save_gate_state,
    validate_gate_state,
)
from scope_package_schema import (
    build_scope_package,
    save_scope_package,
    write_scope_ref_mirror,
)


def _refs(
    tmp_path: Path,
    *,
    cycle_id: str = "feat-common",
    stage: str = "lulu-design",
    scope: Path | None = None,
    intent: list[Path] | None = None,
    norm: list[Path] | None = None,
    scope_ref: DeliveredRef | None | object = ...,
):
    parent = scope if scope is not None else tmp_path / "parent.md"
    if scope is None:
        parent.write_text("# parent\n", encoding="utf-8")
    intent_refs = [
        DeliveredRef(type="lulu-spec", path=str(path.resolve()))
        for path in (intent or [])
    ]
    norm_refs = [
        DeliveredRef(type="norm", path=str(path.resolve()))
        for path in (norm or [])
    ]
    resolved_scope = (
        DeliveredRef(type="scope", path=str(parent.resolve()))
        if scope_ref is ...
        else scope_ref
    )
    write_resolved_refs(
        tmp_path,
        cycle_id=cycle_id,
        stage=stage,
        run_mode="tech",
        scope_ref=resolved_scope,
        intent_baseline_refs=intent_refs,
        norm_constraint_refs=norm_refs,
    )
    return strict_load_resolved_refs(
        tmp_path, expected_cycle_id=cycle_id, expected_stage=stage
    )


class TestStrictResolvedRefs:
    def test_empty_arrays_are_valid(self, tmp_path: Path):
        refs = _refs(tmp_path)
        assert refs.intent_baseline_refs == []
        assert refs.norm_constraint_refs == []
        assert refs.scope_ref is not None

    def test_missing_field_fails(self, tmp_path: Path):
        _refs(tmp_path)
        path = tmp_path / "resolved-refs.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        del data["intent_baseline_refs"]
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ResolvedRefsError, match="intent_baseline_refs"):
            strict_load_resolved_refs(tmp_path)

    def test_illegal_entry_fails_instead_of_drop(self, tmp_path: Path):
        _refs(tmp_path)
        path = tmp_path / "resolved-refs.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["intent_baseline_refs"] = [{"type": "lulu-spec"}]
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ResolvedRefsError, match="path"):
            strict_load_resolved_refs(tmp_path)

    def test_cycle_mismatch_fails(self, tmp_path: Path):
        _refs(tmp_path, cycle_id="feat-a")
        with pytest.raises(ResolvedRefsError, match="cycle_id mismatch"):
            strict_load_resolved_refs(tmp_path, expected_cycle_id="feat-b")


class TestComposeCommonDimensions:
    def test_order_and_empty_skip(self, tmp_path: Path):
        refs = _refs(tmp_path)
        parent = Path(refs.scope_ref.path)
        dims, skip = compose_common_dimensions(
            refs, parent_sot=parent, project_root=tmp_path
        )
        assert [d["id"] for d in dims] == list(COMMON_DIMENSION_IDS)
        assert skip == {
            "intent-fidelity": SKIP_EMPTY_INTENT,
            "norm-conformance": SKIP_EMPTY_NORM,
        }
        assert dims[0]["sots"] == []
        assert dims[1]["sots"] == [{"ref": parent.as_posix()}]
        assert dims[2]["sots"] == []

    def test_nonempty_intent_binds_and_does_not_skip(self, tmp_path: Path):
        intent = tmp_path / "spec.md"
        intent.write_text("# spec\n", encoding="utf-8")
        refs = _refs(tmp_path, intent=[intent])
        dims, skip = compose_common_dimensions(
            refs, parent_sot=Path(refs.scope_ref.path), project_root=tmp_path
        )
        assert "intent-fidelity" not in skip
        assert dims[0]["sots"] == [{"ref": intent.resolve().as_posix()}]

    def test_missing_intent_path_fails(self, tmp_path: Path):
        refs = _refs(tmp_path, intent=[tmp_path / "missing-spec.md"])
        with pytest.raises(ComposeCommonEvalError, match="missing or unreadable"):
            compose_common_dimensions(
                refs, parent_sot=Path(refs.scope_ref.path), project_root=tmp_path
            )

    def test_symbol_collision_fails(self):
        common = [{"id": "intent-fidelity"}]
        stage = [
            {"id": "codebase-consistency", "legacy_alias": "e2"},
            {"id": "other-dim", "legacy_alias": "codebase-consistency"},
        ]
        with pytest.raises(ComposeCommonEvalError, match="symbol collision"):
            merge_common_and_stage(common, stage)

    def test_stage_may_not_redeclare_common_id(self):
        common = [{"id": "intent-fidelity"}]
        stage = [{"id": "intent-fidelity"}]
        with pytest.raises(ComposeCommonEvalError, match="common dimension"):
            merge_common_and_stage(common, stage)


class TestParentContinuity:
    def test_direct_document(self, tmp_path: Path):
        parent = tmp_path / "parent.md"
        parent.write_text("# parent\n", encoding="utf-8")
        refs = _refs(tmp_path, scope=parent)
        resolved = resolve_parent_continuity_sot(
            tmp_path,
            focus_l="L1",
            project_root=tmp_path,
            scope_ref=refs.scope_ref,
        )
        assert resolved == parent.resolve()

    def test_missing_scope_fails(self, tmp_path: Path):
        with pytest.raises(ComposeCommonEvalError, match="scope_ref missing"):
            resolve_parent_continuity_sot(
                tmp_path,
                focus_l="L1",
                project_root=tmp_path,
                scope_ref=None,
            )

    def test_scope_package_uses_focus_mirror(self, tmp_path: Path):
        src1 = tmp_path / "l1.md"
        src2 = tmp_path / "l2.md"
        src1.write_text("# L1\n", encoding="utf-8")
        src2.write_text("# L2\n", encoding="utf-8")
        package = build_scope_package(
            [
                {"id": "L1", "title": "One", "source_path": str(src1.resolve())},
                {"id": "L2", "title": "Two", "source_path": str(src2.resolve())},
            ]
        )
        pkg_path = save_scope_package(tmp_path, package)
        write_scope_ref_mirror(tmp_path, "L1", source_path=str(src1.resolve()))
        write_scope_ref_mirror(tmp_path, "L2", source_path=str(src2.resolve()))
        (tmp_path / "L1").mkdir(exist_ok=True)
        (tmp_path / "L2").mkdir(exist_ok=True)
        scope_ref = DeliveredRef(type="scope", path=str(pkg_path.resolve()))
        resolved = resolve_parent_continuity_sot(
            tmp_path,
            focus_l="L2",
            project_root=tmp_path,
            scope_ref=scope_ref,
        )
        assert resolved == src2.resolve()

    def test_missing_mirror_fails(self, tmp_path: Path):
        src1 = tmp_path / "l1.md"
        src1.write_text("# L1\n", encoding="utf-8")
        package = build_scope_package(
            [{"id": "L1", "title": "One", "source_path": str(src1.resolve())}]
        )
        pkg_path = save_scope_package(tmp_path, package)
        scope_ref = DeliveredRef(type="scope", path=str(pkg_path.resolve()))
        with pytest.raises(ComposeCommonEvalError, match="mirror"):
            resolve_parent_continuity_sot(
                tmp_path,
                focus_l="L1",
                project_root=tmp_path,
                scope_ref=scope_ref,
            )

    def test_stale_mirror_fails(self, tmp_path: Path):
        src1 = tmp_path / "l1.md"
        stale = tmp_path / "stale.md"
        src1.write_text("# L1\n", encoding="utf-8")
        stale.write_text("# stale\n", encoding="utf-8")
        package = build_scope_package(
            [{"id": "L1", "title": "One", "source_path": str(src1.resolve())}]
        )
        pkg_path = save_scope_package(tmp_path, package)
        write_scope_ref_mirror(tmp_path, "L1", source_path=str(stale.resolve()))
        scope_ref = DeliveredRef(type="scope", path=str(pkg_path.resolve()))
        with pytest.raises(ComposeCommonEvalError, match="stale"):
            resolve_parent_continuity_sot(
                tmp_path,
                focus_l="L1",
                project_root=tmp_path,
                scope_ref=scope_ref,
            )


class TestRetiredG5:
    def test_g4_close_becomes_complete(self):
        state = init_gate_state(cycle_id="c1", stage="lulu-design")
        for gate in ("G1", "G2", "G3", "G4"):
            state = close_gate(state, gate)
        assert state["active_gate"] == "complete"
        assert validate_gate_state(state) == []

    def test_active_gate_g5_is_incompatible(self, tmp_path: Path):
        state = init_gate_state(cycle_id="c1", stage="lulu-design")
        for gate in ("G1", "G2", "G3", "G4"):
            state = close_gate(state, gate)
        state["active_gate"] = "G5"
        path = tmp_path / "inductive-gate-state.json"
        path.write_text(json.dumps(state), encoding="utf-8")
        with pytest.raises(ValueError, match="G5 is retired"):
            load_gate_state(path)
        errors = validate_gate_state(state)
        assert any("G5 is retired" in item for item in errors)
        assert not any("complete" == item for item in errors)
