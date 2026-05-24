#!/usr/bin/env python3
"""Tests for t2: STAGE constant + feature-first session_base_dir in all 5 workflow_common.py files."""

import importlib.util
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2]  # lulu-dev-skills/
_STAGES = ["diagnostic", "product", "tech", "work-order", "code"]
_FID = "20260524143022-02cd7e6e"


def _load_wc(stage: str):
    """Load a stage's workflow_common.py as a uniquely-named module."""
    path = _SRC / "lulu-dev-workflow" / stage / "scripts" / "workflow_common.py"
    mod_name = f"wc_{stage.replace('-', '_')}"
    # Remove cached version so each test gets a fresh load
    sys.modules.pop(mod_name, None)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# STAGE constant
# ---------------------------------------------------------------------------

class TestStageConstant:
    @pytest.mark.parametrize("stage", _STAGES)
    def test_stage_constant_exists(self, stage):
        mod = _load_wc(stage)
        assert hasattr(mod, "STAGE"), f"{stage}: missing module-level STAGE constant"

    @pytest.mark.parametrize("stage", _STAGES)
    def test_stage_constant_matches_stage_name(self, stage):
        mod = _load_wc(stage)
        assert mod.STAGE == stage, f"{stage}: STAGE={mod.STAGE!r}, expected {stage!r}"


# ---------------------------------------------------------------------------
# session_base_dir — feature-first path structure
# ---------------------------------------------------------------------------

class TestSessionBaseDir:
    @pytest.mark.parametrize("stage", _STAGES)
    def test_returns_feature_first_path(self, stage):
        mod = _load_wc(stage)
        result = mod.session_base_dir(_FID)
        assert result == mod.CACHE_DIR / _FID / stage

    @pytest.mark.parametrize("stage", _STAGES)
    def test_feature_id_is_second_to_last_part(self, stage):
        mod = _load_wc(stage)
        result = mod.session_base_dir(_FID)
        assert result.parts[-2] == _FID

    @pytest.mark.parametrize("stage", _STAGES)
    def test_stage_name_is_last_part(self, stage):
        mod = _load_wc(stage)
        result = mod.session_base_dir(_FID)
        assert result.parts[-1] == stage

    def test_feature_id_with_hyphen_no_escaping(self):
        mod = _load_wc("tech")
        result = mod.session_base_dir(_FID)
        assert _FID in str(result)
        assert "%" not in str(result)

    @pytest.mark.parametrize("fid", [
        "20260101000000-aaaaaaaa",
        "20991231235959-ffffffff",
        "20260524143022-02cd7e6e",
    ])
    def test_accepts_any_string_feature_id_without_error(self, fid):
        mod = _load_wc("tech")
        result = mod.session_base_dir(fid)
        assert fid in str(result)


# ---------------------------------------------------------------------------
# code stage: code_hot_root must NOT be called by session_base_dir
# ---------------------------------------------------------------------------

class TestCodeStageConstraints:
    def test_session_base_dir_does_not_call_code_hot_root(self):
        mod = _load_wc("code")
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
        mod = _load_wc("code")
        assert callable(mod.code_hot_root)

    def test_code_hot_root_source_has_archive_only_comment(self):
        path = _SRC / "lulu-dev-workflow/code/scripts/workflow_common.py"
        source = path.read_text(encoding="utf-8")
        assert "# archive-only" in source, (
            "code/workflow_common.py: code_hot_root is missing '# archive-only' comment"
        )
