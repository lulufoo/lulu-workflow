#!/usr/bin/env python3
"""Tests for t8b: start.py gate integration (check_gate, re-open, back-fill, get_topic_doc).

All 5 start.py files (product-plan, tech-plan, tech-work-order, tech-code, diagnostic) must
integrate check_gate, current_effective_delivered, invalidate_downstream, and get_topic_doc
before creating a new session.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2]          # lulu-dev-skills/
_LDEV = _SRC / "lulu-dev-workflow"
_CONFIG_DIR = _LDEV / "config"

_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}
_CYCLE_ID = "20260524143022-02cd7e6e"
_TOPIC_ID = "topic-20260101000000-deadbeef"

_STAGES_WITH_GATE = ["product-plan", "tech-plan", "tech-work-order", "tech-code"]
_ALL_STAGES = ["diagnostic", "product-plan", "tech-plan", "tech-work-order", "tech-code"]

# Feature cycle order (matches config/state-machine.json)
_FEATURE_CYCLE = [
    "product-diagnostic", "product-plan", "tech-diagnostic",
    "tech-plan", "tech-work-order", "tech-code",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _start_py(stage: str) -> Path:
    return _LDEV / stage / "scripts" / "start.py"


def _scripts_dir(stage: str) -> Path:
    return _LDEV / stage / "scripts"


def _cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"


def _make_cycles_json(cache_dir: Path, cycle_id: str, extra: dict = None, name: str = "Test Cycle") -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cj = cache_dir / "cycles.json"
    data = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    meta = {"name": name, "execution_mode": "copilot"}
    if extra:
        meta.update(extra)
    data[cycle_id] = meta
    cj.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_session(
    cache_dir: Path,
    cycle_id: str,
    stage: str,
    revision: str,
    state: str,
    updated_at: str = "2026-06-01T00:00:00+00:00",
) -> Path:
    """Create a workflow-state.md at hook_guard path convention (stage/rN/)."""
    session_dir = cache_dir / cycle_id / stage / revision
    session_dir.mkdir(parents=True, exist_ok=True)
    ws = session_dir / "workflow-state.md"
    ws.write_text(
        f"---\ncurrent_state: {state}\nupdated_at: {updated_at}\n---\n",
        encoding="utf-8",
    )
    return ws


def _stage_extra_args(stage: str, tmp_path: Path) -> list:
    """Required extra CLI args for each stage start.py."""
    if stage in ("diagnostic", "product-plan"):
        return []
    if stage == "tech-plan":
        return ["--run-mode", "tech"]
    if stage == "tech-work-order":
        tech_ref = tmp_path / "tech-doc.md"
        tech_ref.write_text("# Tech Doc\n", encoding="utf-8")
        return ["--tech-ref", str(tech_ref)]
    if stage == "tech-code":
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


def _run_start(
    stage: str,
    tmp_path: Path,
    cycle_id: str = _CYCLE_ID,
    extra_args: list = None,
) -> subprocess.CompletedProcess:
    args = extra_args if extra_args is not None else _stage_extra_args(stage, tmp_path)
    cmd = [
        sys.executable, str(_start_py(stage)),
        "--project-root", str(tmp_path),
        "--cycle-id", cycle_id,
    ] + args
    return subprocess.run(
        cmd, capture_output=True, text=True, env=_ENV_COPILOT,
        cwd=str(_scripts_dir(stage)),
    )


def _all_prior_delivered(cache_dir: Path, cycle_id: str, to_stage: str) -> None:
    """Create Delivered sessions for all stages prior to to_stage in feature cycle."""
    if to_stage not in _FEATURE_CYCLE:
        return
    idx = _FEATURE_CYCLE.index(to_stage)
    for s in _FEATURE_CYCLE[:idx]:
        _make_session(cache_dir, cycle_id, s, "r1", "Delivered")


# ---------------------------------------------------------------------------
# TestGateBlocked
# ---------------------------------------------------------------------------

class TestGateBlocked:
    def test_prior_drafting_exits_1(self, tmp_path):
        """Gate blocked: prior stage Drafting → exit 1 with 'Gate blocked' on stderr."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "product-diagnostic", "r1", "Drafting")
        result = _run_start("product-plan", tmp_path)
        assert result.returncode == 1
        assert "Gate blocked" in result.stderr

    def test_gate_blocked_no_session_created(self, tmp_path):
        """Gate blocked → product-plan session file not created."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "product-diagnostic", "r1", "Drafting")
        _run_start("product-plan", tmp_path)
        plan_dir = cd / _CYCLE_ID / "product" / "plan"
        assert not plan_dir.exists() or not any(plan_dir.rglob("workflow-state.md"))

    def test_intermediate_drafting_blocks_downstream(self, tmp_path):
        """Intermediate stage Drafting blocks further downstream stages."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "product-diagnostic", "r1", "Delivered")
        _make_session(cd, _CYCLE_ID, "product-plan", "r1", "Drafting")
        result = _run_start("tech-plan", tmp_path)
        assert result.returncode == 1
        assert "Gate blocked" in result.stderr


# ---------------------------------------------------------------------------
# TestGatePasses
# ---------------------------------------------------------------------------

class TestGatePasses:
    def test_no_prior_sessions_product_plan(self, tmp_path):
        """No prior sessions → gate passes."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        result = _run_start("product-plan", tmp_path)
        assert result.returncode == 0, result.stderr

    def test_prior_delivered_allows_product_plan(self, tmp_path):
        """Prior stage Delivered → gate passes."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "product-diagnostic", "r1", "Delivered")
        result = _run_start("product-plan", tmp_path)
        assert result.returncode == 0, result.stderr

    def test_all_prior_delivered_tech_plan(self, tmp_path):
        """All prior stages Delivered → tech-plan gate passes."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _all_prior_delivered(cd, _CYCLE_ID, "tech-plan")
        result = _run_start("tech-plan", tmp_path)
        assert result.returncode == 0, result.stderr

    def test_diagnostic_always_passes(self, tmp_path):
        """diagnostic stage not in cycle → gate always OK."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "product-diagnostic", "r1", "Drafting")
        result = _run_start("diagnostic", tmp_path)
        assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# TestReopen
# ---------------------------------------------------------------------------

class TestReopen:
    def test_marks_historical_true(self, tmp_path):
        """Re-open: to_stage Delivered session gets historical: true in frontmatter."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        ws = _make_session(cd, _CYCLE_ID, "product-plan", "r1", "Delivered")
        result = _run_start("product-plan", tmp_path)
        assert result.returncode == 0, result.stderr
        assert "historical: true" in ws.read_text(encoding="utf-8")

    def test_old_revision_file_preserved(self, tmp_path):
        """Re-open must NOT delete old revision files."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        ws = _make_session(cd, _CYCLE_ID, "product-plan", "r1", "Delivered")
        _run_start("product-plan", tmp_path)
        assert ws.exists(), "Old revision workflow-state.md must still exist"

    def test_invalidates_downstream(self, tmp_path):
        """Re-open: downstream stages are Invalidated."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "product-plan", "r1", "Delivered")
        downstream_ws = _make_session(cd, _CYCLE_ID, "tech-diagnostic", "r1", "Delivered")
        result = _run_start("product-plan", tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Invalidated" in downstream_ws.read_text(encoding="utf-8")

    def test_creates_new_session_after_reopen(self, tmp_path):
        """Re-open + gate passes → new session is still created."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "product-plan", "r1", "Delivered")
        result = _run_start("product-plan", tmp_path)
        assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# TestBackfill
# ---------------------------------------------------------------------------

class TestBackfill:
    def test_invalidates_later_delivered_stages(self, tmp_path):
        """Back-fill: to_stage < latest Delivered → invalidate_downstream from to_stage."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        # product-diagnostic: Delivered (gate OK for product-plan)
        _make_session(cd, _CYCLE_ID, "product-diagnostic", "r1", "Delivered")
        # No product-plan session (re-open won't trigger)
        # Later stages Delivered → back-fill fires
        tech_diag_ws = _make_session(cd, _CYCLE_ID, "tech-diagnostic", "r1", "Delivered")
        tech_plan_ws = _make_session(cd, _CYCLE_ID, "tech-plan", "r1", "Delivered")
        result = _run_start("product-plan", tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Invalidated" in tech_diag_ws.read_text(encoding="utf-8")
        assert "Invalidated" in tech_plan_ws.read_text(encoding="utf-8")

    def test_no_backfill_when_no_later_delivered(self, tmp_path):
        """No back-fill when no later stages are Delivered."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "product-diagnostic", "r1", "Delivered")
        result = _run_start("product-plan", tmp_path)
        assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# TestGetTopicDoc
# ---------------------------------------------------------------------------

class TestGetTopicDoc:
    def test_topic_id_no_topics_json_exits_1(self, tmp_path):
        """Feature has topic_id but cycles.json absent → ValueError → exit 1."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        result = _run_start("product-plan", tmp_path)
        assert result.returncode == 1
        assert "Error" in result.stderr or "topic" in result.stderr.lower()

    def test_topic_id_no_topics_json_no_session(self, tmp_path):
        """ValueError prevents session creation."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        _run_start("product-plan", tmp_path)
        plan_dir = cd / _CYCLE_ID / "product" / "plan"
        assert not plan_dir.exists() or not any(plan_dir.rglob("workflow-state.md"))

    def test_no_topic_id_session_created(self, tmp_path):
        """No topic_id → get_topic_doc returns None → session created normally."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        result = _run_start("product-plan", tmp_path)
        assert result.returncode == 0, result.stderr

    def test_valid_topic_no_delivered_session_created(self, tmp_path):
        """Valid topic but no Delivered session for it → None → session created."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        _make_cycles_json(cd, _TOPIC_ID)
        result = _run_start("product-plan", tmp_path)
        assert result.returncode == 0, result.stderr

    def test_topic_id_not_in_topics_json_exits_1(self, tmp_path):
        """topic_id not in cycles.json → ValueError → exit 1."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        _make_cycles_json(cd, "topic-other-000-aabbccdd")
        result = _run_start("product-plan", tmp_path)
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# TestAllStagesGateIntegration
# ---------------------------------------------------------------------------

class TestAllStagesGateIntegration:
    """Verify all 5 start.py files carry the gate integration."""

    @pytest.mark.parametrize("stage", _STAGES_WITH_GATE)
    def test_gate_blocked_all_stages(self, stage, tmp_path):
        """Each gated start.py exits 1 when product-diagnostic is Drafting."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "product-diagnostic", "r1", "Drafting")
        result = _run_start(stage, tmp_path)
        assert result.returncode == 1, (
            f"{stage}: expected exit 1 when product-diagnostic is Drafting"
        )
        assert "Gate blocked" in result.stderr

    @pytest.mark.parametrize("stage", _ALL_STAGES)
    def test_topic_missing_topics_json_all_stages(self, stage, tmp_path):
        """All start.py: feature with topic_id + no cycles.json → exit 1."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        _all_prior_delivered(cd, _CYCLE_ID, stage)
        result = _run_start(stage, tmp_path)
        assert result.returncode == 1, (
            f"{stage}: expected exit 1 due to missing cycles.json"
        )

    @pytest.mark.parametrize("stage", _ALL_STAGES)
    def test_reopen_marks_historical_all_stages(self, stage, tmp_path):
        """All start.py mark historical when their to_stage has a Delivered session."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        # to_stage = stage for all (they share the same stage name convention)
        old_ws = _make_session(cd, _CYCLE_ID, stage, "r1", "Delivered")
        _all_prior_delivered(cd, _CYCLE_ID, stage)
        result = _run_start(stage, tmp_path)
        assert result.returncode == 0, f"{stage}: {result.stderr}"
        assert "historical: true" in old_ws.read_text(encoding="utf-8"), (
            f"{stage}: expected historical: true in old session"
        )
