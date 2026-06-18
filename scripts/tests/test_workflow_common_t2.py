#!/usr/bin/env python3
"""Tests for t2: STAGE constant + feature-first session_base_dir in all 5 workflow_common.py files."""

import importlib.util
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3]  # lulu-dev-skills/
_STAGES = ["diagnostic", "product-plan", "tech-work-order", "tech-code"]
# tech-plan uses compose-kernel/scripts/core/workflow_common.py (no STAGE / session_base_dir).
_FID = "20260524143022-02cd7e6e"

_EXPECTED_CACHE_SUBDIR = {
    "diagnostic": "diagnostic",
    "product-plan": "product/plan",
    "tech-work-order": "tech/work-order",
    "tech-code": "tech/code",
}


_STAGE_WC = {
    "diagnostic": "dx_workflow_common.py",
    "product-plan": "pp_workflow_common.py",
    "tech-work-order": "two_workflow_common.py",
    "tech-code": "tc_workflow_common.py",
}


def _workflow_common_path(stage: str) -> Path:
    root = _SRC / "lulu-dev-workflow"
    return root / stage / "scripts" / _STAGE_WC[stage]


def _load_wc(stage: str):
    """Load a stage's workflow_common.py as a uniquely-named module."""
    path = _workflow_common_path(stage)
    mod_name = f"wc_{stage.replace('-', '_')}"
    sys.modules.pop(mod_name, None)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _expected_session_base(mod, cycle_id: str) -> Path:
    subdir = getattr(mod, "CACHE_SUBDIR", mod.STAGE)
    return mod.CACHE_DIR / cycle_id / subdir


class TestStageConstant:
    @pytest.mark.parametrize("stage", _STAGES)
    def test_stage_constant_exists(self, stage):
        mod = _load_wc(stage)
        assert hasattr(mod, "STAGE"), f"{stage}: missing module-level STAGE constant"

    @pytest.mark.parametrize("stage", _STAGES)
    def test_stage_constant_matches_stage_name(self, stage):
        mod = _load_wc(stage)
        assert mod.STAGE == stage, f"{stage}: STAGE={mod.STAGE!r}, expected {stage!r}"


class TestSessionBaseDir:
    @pytest.mark.parametrize("stage", _STAGES)
    def test_returns_feature_first_path(self, stage):
        mod = _load_wc(stage)
        result = mod.session_base_dir(_FID)
        assert result == _expected_session_base(mod, _FID)

    @pytest.mark.parametrize("stage", _STAGES)
    def test_cycle_id_present_in_path(self, stage):
        mod = _load_wc(stage)
        result = mod.session_base_dir(_FID)
        assert _FID in result.parts

    @pytest.mark.parametrize("stage", _STAGES)
    def test_cache_subdir_matches_line_layout(self, stage):
        mod = _load_wc(stage)
        result = mod.session_base_dir(_FID)
        expected = _EXPECTED_CACHE_SUBDIR[stage]
        assert str(result).endswith(f"{_FID}/{expected}")

    def test_cycle_id_with_hyphen_no_escaping(self):
        mod = _load_wc("product-plan")
        result = mod.session_base_dir(_FID)
        assert _FID in str(result)
        assert "%" not in str(result)

    @pytest.mark.parametrize("fid", [
        "20260101000000-aaaaaaaa",
        "20991231235959-ffffffff",
        "20260524143022-02cd7e6e",
    ])
    def test_accepts_any_string_cycle_id_without_error(self, fid):
        mod = _load_wc("product-plan")
        result = mod.session_base_dir(fid)
        assert fid in str(result)


class TestCodeStageConstraints:
    def test_session_base_dir_does_not_call_code_hot_root(self):
        mod = _load_wc("tech-code")
        called = []
        original_fn = mod.code_hot_root

        def spy():
            called.append(True)
            return original_fn()

        mod.code_hot_root = spy
        mod.session_base_dir(_FID)
        assert called == [], (
            "session_base_dir must NOT call code_hot_root (it should use STAGE directly)"
        )

    def test_code_hot_root_function_still_exists(self):
        mod = _load_wc("tech-code")
        assert callable(mod.code_hot_root)

    def test_code_hot_root_source_has_archive_only_comment(self):
        path = _SRC / "lulu-dev-workflow/tech-code/scripts/tc_workflow_common.py"
        source = path.read_text(encoding="utf-8")
        assert "# archive-only" in source
