#!/usr/bin/env python3
"""Tests for t3: start.py --feature-id + archive call deferral in all 5 stages."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2]  # lulu-dev-skills/
_STAGES = ["diagnostic", "product-plan", "tech-plan", "tech-work-order", "tech-code"]
_FID = "20260524143022-02cd7e6e"
_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}


def _start_py(stage: str) -> Path:
    return _SRC / "lulu-dev-workflow" / stage / "scripts" / "start.py"


def _scripts_dir(stage: str) -> Path:
    return _SRC / "lulu-dev-workflow" / stage / "scripts"


def _cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"


# ---------------------------------------------------------------------------
# Source inspection: --feature-id replaces --conversation-id
# ---------------------------------------------------------------------------

class TestArgparseSource:
    @pytest.mark.parametrize("stage", _STAGES)
    def test_feature_id_arg_declared(self, stage):
        src = _start_py(stage).read_text(encoding="utf-8")
        assert '"--feature-id"' in src or "'--feature-id'" in src, (
            f"{stage}/start.py: --feature-id not declared in argparse"
        )

    @pytest.mark.parametrize("stage", _STAGES)
    def test_conversation_id_arg_removed(self, stage):
        src = _start_py(stage).read_text(encoding="utf-8")
        # Must not have an active (non-commented) add_argument for --conversation-id
        active_lines = [
            line for line in src.splitlines()
            if (
                'add_argument("--conversation-id"' in line
                or "add_argument('--conversation-id'" in line
            ) and not line.lstrip().startswith("#")
        ]
        assert active_lines == [], (
            f"{stage}/start.py: --conversation-id still declared in argparse: {active_lines}"
        )


# ---------------------------------------------------------------------------
# Source inspection: archive calls commented with # archive: deferred
# ---------------------------------------------------------------------------

class TestArchiveDeferred:
    @pytest.mark.parametrize("stage", _STAGES)
    def test_archive_deferred_comment_present(self, stage):
        src = _start_py(stage).read_text(encoding="utf-8")
        assert "# archive: deferred" in src, (
            f"{stage}/start.py: '# archive: deferred' comment not found"
        )

    @pytest.mark.parametrize("stage", _STAGES)
    def test_run_archive_call_is_not_active(self, stage):
        src = _start_py(stage).read_text(encoding="utf-8")
        import re
        # Active (not commented out) call to run_archive(
        active_calls = [
            line for line in src.splitlines()
            if re.search(r"run_archive\(", line) and not line.lstrip().startswith("#")
        ]
        assert active_calls == [], (
            f"{stage}/start.py: run_archive() still has active (uncommented) calls: {active_calls}"
        )


# ---------------------------------------------------------------------------
# Subprocess: --feature-id recognized, --conversation-id rejected
# ---------------------------------------------------------------------------

class TestArgparseBehavior:
    def _run_missing_args(self, stage: str):
        """Run start.py with no args — expect error."""
        return subprocess.run(
            [sys.executable, str(_start_py(stage))],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )

    def _run_with_conv_id(self, stage: str, tmp_path: Path, extra: list = None):
        cmd = [
            sys.executable, str(_start_py(stage)),
            "--project-root", str(tmp_path),
            "--conversation-id", _FID,
        ]
        if extra:
            cmd.extend(extra)
        return subprocess.run(
            cmd, capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )

    def test_feature_id_missing_diagnostic_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(_start_py("diagnostic")), "--project-root", "."],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("diagnostic")),
        )
        assert result.returncode != 0

    def test_conversation_id_rejected_diagnostic(self, tmp_path):
        result = self._run_with_conv_id("diagnostic", tmp_path)
        assert result.returncode != 0, (
            "diagnostic/start.py: --conversation-id should be rejected but was accepted"
        )


# ---------------------------------------------------------------------------
# Subprocess: successful run creates session file at feature-first path
# ---------------------------------------------------------------------------

class TestSessionPath:
    def _run_diagnostic(self, tmp_path):
        return subprocess.run(
            [sys.executable, str(_start_py("diagnostic")),
             "--project-root", str(tmp_path),
             "--feature-id", _FID],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("diagnostic")),
        )

    def _run_product(self, tmp_path):
        return subprocess.run(
            [sys.executable, str(_start_py("product-plan")),
             "--project-root", str(tmp_path),
             "--feature-id", _FID],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("product-plan")),
        )

    def _run_tech(self, tmp_path):
        return subprocess.run(
            [sys.executable, str(_start_py("tech-plan")),
             "--project-root", str(tmp_path),
             "--feature-id", _FID,
             "--run-mode", "tech"],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("tech-plan")),
        )

    def _run_work_order(self, tmp_path):
        # tech-work-order requires --tech-ref (existing file)
        tech_ref = tmp_path / "tech-doc.md"
        tech_ref.write_text("# Tech Doc\n", encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(_start_py("tech-work-order")),
             "--project-root", str(tmp_path),
             "--feature-id", _FID,
             "--tech-ref", str(tech_ref)],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("tech-work-order")),
        )

    def _run_code(self, tmp_path):
        # tech-code requires --mode and --task-list-ref (existing file with table)
        task_list = tmp_path / "task-list.md"
        task_list.write_text(
            "# Task List\n\n"
            "| task_id | 标题 | 目标文件 | 依赖 | TDD 豁免 |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| t1 | test task | `scripts/foo.py` | — | 否 |\n",
            encoding="utf-8",
        )
        return subprocess.run(
            [sys.executable, str(_start_py("tech-code")),
             "--project-root", str(tmp_path),
             "--feature-id", _FID,
             "--mode", "task-from-work-order",
             "--task-list-ref", str(task_list)],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("tech-code")),
        )

    def test_diagnostic_exits_zero(self, tmp_path):
        result = self._run_diagnostic(tmp_path)
        assert result.returncode == 0, result.stderr

    def test_diagnostic_session_file_at_feature_first_path(self, tmp_path):
        self._run_diagnostic(tmp_path)
        ss = _cache_dir(tmp_path) / _FID / "diagnostic" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def _run_diagnostic_with_stage(self, tmp_path, stage: str):
        return subprocess.run(
            [sys.executable, str(_start_py("diagnostic")),
             "--project-root", str(tmp_path),
             "--feature-id", _FID,
             "--stage", stage],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("diagnostic")),
        )

    def test_product_diagnostic_stage_exits_zero(self, tmp_path):
        result = self._run_diagnostic_with_stage(tmp_path, "product-diagnostic")
        assert result.returncode == 0, result.stderr

    def test_product_diagnostic_stage_writes_nested_path(self, tmp_path):
        self._run_diagnostic_with_stage(tmp_path, "product-diagnostic")
        ss = _cache_dir(tmp_path) / _FID / "product" / "diagnostic" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def test_tech_diagnostic_stage_writes_nested_path(self, tmp_path):
        self._run_diagnostic_with_stage(tmp_path, "tech-diagnostic")
        ss = _cache_dir(tmp_path) / _FID / "tech" / "diagnostic" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def test_product_diagnostic_active_context_stage_value(self, tmp_path):
        import json
        self._run_diagnostic_with_stage(tmp_path, "product-diagnostic")
        ctx = _cache_dir(tmp_path) / "active-context.json"
        assert ctx.exists(), f"Expected active-context.json at {ctx}"
        data = json.loads(ctx.read_text(encoding="utf-8"))
        assert data.get("stage") == "product-diagnostic", f"stage mismatch: {data}"

    def test_product_session_file_at_feature_first_path(self, tmp_path):
        self._run_product(tmp_path)
        ss = _cache_dir(tmp_path) / _FID / "product" / "plan" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def test_tech_session_file_at_feature_first_path(self, tmp_path):
        self._run_tech(tmp_path)
        ss = _cache_dir(tmp_path) / _FID / "tech" / "plan" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def test_work_order_session_file_at_feature_first_path(self, tmp_path):
        self._run_work_order(tmp_path)
        ss = _cache_dir(tmp_path) / _FID / "tech-work-order" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def test_code_session_file_at_feature_first_path(self, tmp_path):
        self._run_code(tmp_path)
        ss = _cache_dir(tmp_path) / _FID / "tech-code" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"
