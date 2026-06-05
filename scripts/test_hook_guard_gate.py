#!/usr/bin/env python3
"""Tests for hook_guard gate functions: has_any_valid_session, current_effective_delivered,
check_gate, get_topic_doc."""

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPTS.parent
_CONFIG_DIR = _SKILL_ROOT / "config"

if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _make_workflow_state(tmp_path: Path, container_id: str, stage: str, revision: str,
                          state: str, updated_at: str = "2026-06-01T00:00:00+00:00") -> Path:
    """Create a workflow-state.md file at the expected session path."""
    session_dir = tmp_path / container_id / stage / revision
    session_dir.mkdir(parents=True, exist_ok=True)
    ws = session_dir / "workflow-state.md"
    ws.write_text(
        f"---\ncurrent_state: {state}\nupdated_at: {updated_at}\n---\n",
        encoding="utf-8",
    )
    return ws


# ---------------------------------------------------------------------------
# has_any_valid_session
# ---------------------------------------------------------------------------

class TestHasAnyValidSession:
    def test_single_non_invalidated_returns_true(self, tmp_path):
        from hook_guard import has_any_valid_session
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered")
        assert has_any_valid_session("feat-a", "tech-plan", tmp_path) is True

    def test_all_invalidated_returns_false(self, tmp_path):
        from hook_guard import has_any_valid_session
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Invalidated")
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r2", "Invalidated")
        assert has_any_valid_session("feat-a", "tech-plan", tmp_path) is False

    def test_no_sessions_returns_false(self, tmp_path):
        from hook_guard import has_any_valid_session
        assert has_any_valid_session("feat-a", "tech-plan", tmp_path) is False

    def test_drafting_counts_as_valid(self, tmp_path):
        from hook_guard import has_any_valid_session
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Drafting")
        assert has_any_valid_session("feat-a", "tech-plan", tmp_path) is True

    def test_old_state_names_ignored(self, tmp_path):
        from hook_guard import has_any_valid_session
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "InProgress")
        assert has_any_valid_session("feat-a", "tech-plan", tmp_path) is False


# ---------------------------------------------------------------------------
# current_effective_delivered
# ---------------------------------------------------------------------------

class TestCurrentEffectiveDelivered:
    def test_single_delivered_returns_true(self, tmp_path):
        from hook_guard import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        assert current_effective_delivered("feat-a", "tech-plan", tmp_path) is True

    def test_latest_non_invalidated_is_drafting_returns_false(self, tmp_path):
        from hook_guard import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r2", "Drafting",
                             "2026-06-02T10:00:00+00:00")
        assert current_effective_delivered("feat-a", "tech-plan", tmp_path) is False

    def test_no_valid_sessions_returns_false(self, tmp_path):
        from hook_guard import current_effective_delivered
        assert current_effective_delivered("feat-a", "tech-plan", tmp_path) is False

    def test_all_invalidated_returns_false(self, tmp_path):
        from hook_guard import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Invalidated")
        assert current_effective_delivered("feat-a", "tech-plan", tmp_path) is False

    def test_multiple_delivered_latest_delivered_returns_true(self, tmp_path):
        from hook_guard import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r2", "Delivered",
                             "2026-06-02T10:00:00+00:00")
        assert current_effective_delivered("feat-a", "tech-plan", tmp_path) is True


# ---------------------------------------------------------------------------
# check_gate  (uses real config files from lulu-dev-workflow/config/)
# ---------------------------------------------------------------------------

class TestCheckGate:
    def test_no_prior_sessions_allows_entry(self, tmp_path):
        from hook_guard import check_gate
        ok, msg = check_gate("feat-a", "product-diagnostic", "feature", tmp_path, _CONFIG_DIR)
        assert ok is True
        assert msg == "OK"

    def test_no_prior_sessions_allows_any_stage(self, tmp_path):
        from hook_guard import check_gate
        ok, msg = check_gate("feat-a", "tech-diagnostic", "feature", tmp_path, _CONFIG_DIR)
        assert ok is True

    def test_prior_delivered_allows_next(self, tmp_path):
        from hook_guard import check_gate
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "Delivered")
        ok, msg = check_gate("feat-a", "product-plan", "feature", tmp_path, _CONFIG_DIR)
        assert ok is True
        assert msg == "OK"

    def test_prior_drafting_blocks_next(self, tmp_path):
        from hook_guard import check_gate
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "Drafting")
        ok, msg = check_gate("feat-a", "product-plan", "feature", tmp_path, _CONFIG_DIR)
        assert ok is False
        assert "product-diagnostic" in msg

    def test_gap_scenario_blocks(self, tmp_path):
        """product-diagnostic Drafting, product-plan missing → tech-diagnostic blocked."""
        from hook_guard import check_gate
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "Drafting")
        ok, msg = check_gate("feat-a", "tech-diagnostic", "feature", tmp_path, _CONFIG_DIR)
        assert ok is False

    def test_topic_cycle_delivered_allows_next(self, tmp_path):
        from hook_guard import check_gate
        _make_workflow_state(tmp_path, "topic-a", "product-diagnostic", "r1", "Delivered")
        ok, msg = check_gate("topic-a", "product-plan", "topic", tmp_path, _CONFIG_DIR)
        assert ok is True


# ---------------------------------------------------------------------------
# get_sessions — unit
# ---------------------------------------------------------------------------

class TestGetSessions:
    def test_returns_empty_when_no_sessions(self, tmp_path):
        from hook_guard import get_sessions
        sessions = get_sessions("feat-a", "tech-plan", tmp_path)
        assert sessions == []

    def test_old_state_names_skipped(self, tmp_path):
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "InProgress")
        sessions = get_sessions("feat-a", "tech-plan", tmp_path)
        assert sessions == []

    def test_returns_session_info_objects(self, tmp_path):
        from hook_guard import get_sessions, SessionInfo
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        sessions = get_sessions("feat-a", "tech-plan", tmp_path)
        assert len(sessions) == 1
        assert isinstance(sessions[0], SessionInfo)
        assert sessions[0].state == "Delivered"
        assert sessions[0].revision == "r1"


# ---------------------------------------------------------------------------
# get_topic_doc
# ---------------------------------------------------------------------------

class TestGetTopicDoc:
    def _write_features_json(self, cache_dir: Path, feature_id: str, meta: dict):
        fj = cache_dir / "features.json"
        data = {}
        if fj.exists():
            data = json.loads(fj.read_text())
        data[feature_id] = meta
        fj.write_text(json.dumps(data), encoding="utf-8")

    def _write_topics_json(self, cache_dir: Path, topic_id: str, meta: dict):
        tj = cache_dir / "topics.json"
        data = {}
        if tj.exists():
            data = json.loads(tj.read_text())
        data[topic_id] = meta
        tj.write_text(json.dumps(data), encoding="utf-8")

    def test_no_topic_id_returns_none(self, tmp_path):
        from hook_guard import get_topic_doc
        self._write_features_json(tmp_path, "feat-a", {"name": "x", "execution_mode": "copilot"})
        result = get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)
        assert result is None

    def test_invalid_topic_id_raises_value_error(self, tmp_path):
        from hook_guard import get_topic_doc
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "copilot",
                                   "topic_id": "topic-20260101000000-deadbeef"})
        # topics.json does not exist → ValueError
        with pytest.raises(ValueError):
            get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)

    def test_tech_code_null_ref_stage_returns_none(self, tmp_path):
        from hook_guard import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "copilot",
                                   "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "copilot"})
        # tech-code maps to null in topic_ref_stage
        result = get_topic_doc("feat-a", "tech-code", tmp_path, _CONFIG_DIR)
        assert result is None

    def test_valid_topic_no_delivered_session_returns_none(self, tmp_path):
        from hook_guard import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "copilot",
                                   "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "copilot"})
        # No session files → None
        result = get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)
        assert result is None
