#!/usr/bin/env python3
"""Tests for t4: container-type routing (topic-id vs cycle-id) in all 5 stages."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2]  # lulu-dev-skills/
_STAGES = ["diagnostic", "product-plan", "tech-plan", "tech-work-order", "tech-code"]

# Use tech-work-order's workflow_common for unit tests of shared functions
_TWO_SCRIPTS = _SRC / "lulu-dev-workflow" / "tech-work-order" / "scripts"
if str(_TWO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_TWO_SCRIPTS))

_CYCLE_ID = "20260524143022-02cd7e6e"
_TOPIC_ID = "topic-20260524143022-aabbccdd"
_CONV_ID = "test-conv-t4-routing"
_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}


def _start_py(stage: str) -> Path:
    return _SRC / "lulu-dev-workflow" / stage / "scripts" / "start.py"


def _scripts_dir(stage: str) -> Path:
    return _SRC / "lulu-dev-workflow" / stage / "scripts"


def _cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"


def _make_cycles_json(cache_dir: Path, cycle_id: str, name: str = "Test Cycle") -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cj = cache_dir / "cycles.json"
    data = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    data[cycle_id] = {"name": name, "execution_mode": "guided"}
    cj.write_text(json.dumps(data, indent=2), encoding="utf-8")





def _stage_extra_args(stage: str, tmp_path: Path) -> list:
    """Return required extra CLI args for each stage."""
    if stage == "diagnostic":
        return []
    elif stage == "product-plan":
        return []
    elif stage == "tech-plan":
        return ["--run-mode", "tech"]
    elif stage == "tech-work-order":
        tech_ref = tmp_path / "tech-doc.md"
        tech_ref.write_text("# Tech Doc\n", encoding="utf-8")
        return ["--tech-ref", str(tech_ref)]
    elif stage == "tech-code":
        task_list = tmp_path / "task-list.md"
        task_list.write_text(
            "# Task List\n\n"
            "| task_id | 标题 | 目标文件 | 依赖 | TDD 豁免 |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| t1 | test task | `scripts/foo.py` | — | 否 |\n",
            encoding="utf-8",
        )
        return ["--mode", "task-from-work-order", "--task-list-ref", str(task_list)]
    return []


# ---------------------------------------------------------------------------
# Unit: detect_cycle_type
# ---------------------------------------------------------------------------


class TestDetectContainerType:
    def test_cycle_id_returns_feature(self):
        from workflow_common import detect_cycle_type

        assert detect_cycle_type(_CYCLE_ID) == "feature"

    def test_topic_id_returns_topic(self):
        from workflow_common import detect_cycle_type

        assert detect_cycle_type(_TOPIC_ID) == "topic"

    def test_plain_string_returns_feature(self):
        from workflow_common import detect_cycle_type

        assert detect_cycle_type("some-random-id") == "feature"

    def test_topic_prefix_canonical(self):
        from workflow_common import detect_cycle_type

        assert detect_cycle_type("topic-20260101000000-aabbccdd") == "topic"


# ---------------------------------------------------------------------------
# Unit: load_container_meta
# ---------------------------------------------------------------------------


class TestLoadContainerMeta:
    def test_feature_reads_features_json(self, tmp_path):
        from workflow_common import load_container_meta

        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        meta = load_container_meta(cd, _CYCLE_ID, "feature")
        assert meta["name"] == "Test Cycle"

    def test_topic_reads_topics_json(self, tmp_path):
        from workflow_common import load_container_meta

        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _TOPIC_ID)
        meta = load_container_meta(cd, _TOPIC_ID, "topic")
        assert meta["name"] == "Test Cycle"

    def test_feature_not_in_features_json_raises(self, tmp_path):
        from workflow_common import load_container_meta

        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, "other-00000000-aaaabbbb")
        with pytest.raises(ValueError):
            load_container_meta(cd, _CYCLE_ID, "feature")

    def test_feature_no_features_json_returns_empty(self, tmp_path):
        """Backward compat: cycles.json absent → return {} (no error)."""
        from workflow_common import load_container_meta

        cd = _cache_dir(tmp_path)
        cd.mkdir(parents=True, exist_ok=True)
        meta = load_container_meta(cd, _CYCLE_ID, "feature")
        assert meta == {}

    def test_topic_absent_topics_json_raises(self, tmp_path):
        from workflow_common import load_container_meta

        cd = _cache_dir(tmp_path)
        cd.mkdir(parents=True, exist_ok=True)
        with pytest.raises(ValueError):
            load_container_meta(cd, _TOPIC_ID, "topic")

    def test_topic_not_in_topics_json_raises(self, tmp_path):
        from workflow_common import load_container_meta

        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, "topic-other-000-aaaabbbb")
        with pytest.raises(ValueError):
            load_container_meta(cd, _TOPIC_ID, "topic")


# ---------------------------------------------------------------------------
# active-context.json gets cycle_type field
# ---------------------------------------------------------------------------


class TestActiveContextContainerType:
    @pytest.mark.parametrize("stage", _STAGES)
    def test_cycle_id_writes_cycle_type_feature(self, stage, tmp_path):
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        extra = _stage_extra_args(stage, tmp_path)
        cmd = [
            sys.executable, str(_start_py(stage)),
            "--project-root", str(tmp_path),
            "--cycle-id", _CYCLE_ID,
            "--conversation-id", _CONV_ID,
        ] + extra
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )
        assert result.returncode == 0, result.stderr
        ctx = cd / "active-context.json"
        assert ctx.exists(), f"active-context.json not found at {ctx}"
        data = json.loads(ctx.read_text(encoding="utf-8"))
        assert _CONV_ID in data, f"conv key missing: {list(data)}"
        assert data[_CONV_ID]["cycle_type"] == "feature"

    @pytest.mark.parametrize("stage", _STAGES)
    def test_topic_id_writes_cycle_type_topic(self, stage, tmp_path):
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _TOPIC_ID)
        extra = _stage_extra_args(stage, tmp_path)
        cmd = [
            sys.executable, str(_start_py(stage)),
            "--project-root", str(tmp_path),
            "--cycle-id", _TOPIC_ID,
            "--conversation-id", _CONV_ID,
        ] + extra
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )
        assert result.returncode == 0, result.stderr
        ctx = cd / "active-context.json"
        assert ctx.exists()
        data = json.loads(ctx.read_text(encoding="utf-8"))
        assert _CONV_ID in data
        assert data[_CONV_ID]["cycle_type"] == "topic"


# ---------------------------------------------------------------------------
# Session path for topic-id is symmetric with cycle-id
# ---------------------------------------------------------------------------


class TestTopicIdSessionPath:
    def test_diagnostic_topic_session_uses_topic_dir(self, tmp_path):
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _TOPIC_ID)
        result = subprocess.run(
            [
                sys.executable, str(_start_py("diagnostic")),
                "--project-root", str(tmp_path),
                "--cycle-id", _TOPIC_ID,
            ],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("diagnostic")),
        )
        assert result.returncode == 0, result.stderr
        ss = cd / _TOPIC_ID / "diagnostic" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def test_product_plan_topic_session_uses_topic_dir(self, tmp_path):
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _TOPIC_ID)
        result = subprocess.run(
            [
                sys.executable, str(_start_py("product-plan")),
                "--project-root", str(tmp_path),
                "--cycle-id", _TOPIC_ID,
            ],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("product-plan")),
        )
        assert result.returncode == 0, result.stderr
        ss = cd / _TOPIC_ID / "product" / "plan" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestContainerRoutingErrors:
    @pytest.mark.parametrize("stage", _STAGES)
    def test_cycle_id_not_in_features_json_exits_nonzero(self, stage, tmp_path):
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, "other-00000000-aaaabbbb")
        extra = _stage_extra_args(stage, tmp_path)
        cmd = [
            sys.executable, str(_start_py(stage)),
            "--project-root", str(tmp_path),
            "--cycle-id", _CYCLE_ID,
        ] + extra
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )
        assert result.returncode != 0, (
            f"{stage}: expected nonzero exit when cycle_id not in cycles.json"
        )

    @pytest.mark.parametrize("stage", _STAGES)
    def test_topic_id_without_topics_json_exits_nonzero(self, stage, tmp_path):
        cd = _cache_dir(tmp_path)
        cd.mkdir(parents=True, exist_ok=True)
        extra = _stage_extra_args(stage, tmp_path)
        cmd = [
            sys.executable, str(_start_py(stage)),
            "--project-root", str(tmp_path),
            "--cycle-id", _TOPIC_ID,
        ] + extra
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )
        assert result.returncode != 0, (
            f"{stage}: expected nonzero exit when cycles.json absent"
        )

    @pytest.mark.parametrize("stage", _STAGES)
    def test_topic_id_not_in_topics_json_exits_nonzero(self, stage, tmp_path):
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, "topic-other-000-aaaabbbb")
        extra = _stage_extra_args(stage, tmp_path)
        cmd = [
            sys.executable, str(_start_py(stage)),
            "--project-root", str(tmp_path),
            "--cycle-id", _TOPIC_ID,
        ] + extra
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )
        assert result.returncode != 0, (
            f"{stage}: expected nonzero exit when topic_id not in cycles.json"
        )


# ---------------------------------------------------------------------------
# Backward compat
# ---------------------------------------------------------------------------


class TestActiveContextBackwardCompat:
    def test_read_entry_without_cycle_type_defaults_to_feature(self, tmp_path):
        """read_all on old-style entries (no cycle_type) must normalize to 'feature'."""
        _scripts = _SRC / "lulu-dev-workflow" / "scripts"
        if str(_scripts) not in sys.path:
            sys.path.insert(0, str(_scripts))
        from active_context import read_all  # noqa: E402

        cd = _cache_dir(tmp_path)
        cd.mkdir(parents=True, exist_ok=True)
        ctx_path = cd / "active-context.json"
        ctx_path.write_text(
            json.dumps({"old-conv-id": {"cycle_id": _CYCLE_ID, "stage": "diagnostic"}}),
            encoding="utf-8",
        )
        data = read_all(tmp_path, "copilot")
        assert "old-conv-id" in data
        assert data["old-conv-id"]["cycle_type"] == "feature"

    def test_old_features_json_without_topic_id_field_works(self, tmp_path):
        """cycles.json entries without topic_id field: cycle-id routing works fine."""
        cd = _cache_dir(tmp_path)
        cd.mkdir(parents=True, exist_ok=True)
        fj = cd / "cycles.json"
        fj.write_text(
            json.dumps({_CYCLE_ID: {"name": "Old Feature", "execution_mode": "guided"}}),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable, str(_start_py("diagnostic")),
                "--project-root", str(tmp_path),
                "--cycle-id", _CYCLE_ID,
                "--conversation-id", _CONV_ID,
            ],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("diagnostic")),
        )
        assert result.returncode == 0, result.stderr
