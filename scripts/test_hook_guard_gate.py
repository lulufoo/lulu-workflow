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


def _make_workflow_state(tmp_path: Path, cycle_id: str, stage: str, revision: str,
                          state: str, updated_at: str = "2026-06-01T00:00:00+00:00") -> Path:
    """Create a workflow-state.md file at the expected session path."""
    session_dir = tmp_path / cycle_id / stage / revision
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
    def _write_features_json(self, cache_dir: Path, cycle_id: str, meta: dict):
        fj = cache_dir / "features.json"
        data = {}
        if fj.exists():
            data = json.loads(fj.read_text())
        data[cycle_id] = meta
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


# ---------------------------------------------------------------------------
# invalidate_downstream
# ---------------------------------------------------------------------------

class TestInvalidateDownstream:
    def test_reopen_product_plan_invalidates_downstream(self, tmp_path):
        """Re-opening product-plan: all downstream stages become Invalidated."""
        from invalidation_hook import invalidate_downstream
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "product-plan", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-diagnostic", "r1", "Drafting")
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-work-order", "r1", "Drafting")

        invalidate_downstream("feat-a", "product-plan", "feature", tmp_path)

        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "tech-diagnostic", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "tech-plan", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "tech-work-order", tmp_path))

    def test_backfill_product_diagnostic_invalidates_product_plan_and_later(self, tmp_path):
        """Back-fill: re-open product-diagnostic → product-plan and all later stages Invalidated."""
        from invalidation_hook import invalidate_downstream
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "product-plan", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-diagnostic", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered")

        invalidate_downstream("feat-a", "product-diagnostic", "feature", tmp_path)

        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "product-plan", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "tech-diagnostic", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "tech-plan", tmp_path))

    def test_from_stage_itself_not_modified(self, tmp_path):
        """from_stage sessions are NOT touched by invalidate_downstream."""
        from invalidation_hook import invalidate_downstream
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "product-plan", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-diagnostic", "r1", "Drafting")

        invalidate_downstream("feat-a", "product-plan", "feature", tmp_path)

        product_plan = get_sessions("feat-a", "product-plan", tmp_path)
        assert len(product_plan) == 1
        assert product_plan[0].state == "Delivered"

    def test_already_invalidated_stays_invalidated_idempotent(self, tmp_path):
        """Idempotent: already-Invalidated session stays Invalidated, no error on repeat call."""
        from invalidation_hook import invalidate_downstream
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "product-plan", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-diagnostic", "r1", "Invalidated")

        invalidate_downstream("feat-a", "product-plan", "feature", tmp_path)
        invalidate_downstream("feat-a", "product-plan", "feature", tmp_path)

        tech_diag = get_sessions("feat-a", "tech-diagnostic", tmp_path)
        assert all(s.state == "Invalidated" for s in tech_diag)

    def test_old_state_names_not_modified(self, tmp_path):
        """Sessions with old state names (InProgress) are skipped — file content unchanged."""
        from invalidation_hook import invalidate_downstream
        session_dir = tmp_path / "feat-a" / "tech-diagnostic" / "r1"
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "workflow-state.md"
        ws.write_text("---\ncurrent_state: InProgress\n---\n", encoding="utf-8")

        invalidate_downstream("feat-a", "product-plan", "feature", tmp_path)

        assert "InProgress" in ws.read_text()


# ---------------------------------------------------------------------------
# Cross-container isolation
# ---------------------------------------------------------------------------

class TestCrossContainerIsolation:
    def test_topic_reopen_does_not_affect_feature_container(self, tmp_path):
        """Re-opening a topic container leaves feature container sessions untouched."""
        from invalidation_hook import invalidate_downstream
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "topic-a", "product-diagnostic", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "product-plan", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "product-plan", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-diagnostic", "r1", "Delivered")

        invalidate_downstream("topic-a", "product-diagnostic", "topic", tmp_path)

        feat_plan = get_sessions("feat-a", "product-plan", tmp_path)
        feat_diag = get_sessions("feat-a", "tech-diagnostic", tmp_path)
        assert all(s.state == "Delivered" for s in feat_plan)
        assert all(s.state == "Delivered" for s in feat_diag)

    def test_topic_reopen_product_diagnostic_invalidates_all_later(self, tmp_path):
        """Topic re-open product-diagnostic → product-plan, tech-diagnostic, tech-plan Invalidated."""
        from invalidation_hook import invalidate_downstream
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "topic-a", "product-plan", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "tech-diagnostic", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "tech-plan", "r1", "Delivered")

        invalidate_downstream("topic-a", "product-diagnostic", "topic", tmp_path)

        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "product-plan", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "tech-diagnostic", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "tech-plan", tmp_path))

    def test_topic_reopen_product_plan_invalidates_tech(self, tmp_path):
        """Topic re-open product-plan → tech-diagnostic, tech-plan Invalidated; product-plan unchanged."""
        from invalidation_hook import invalidate_downstream
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "topic-a", "product-plan", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "tech-diagnostic", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "tech-plan", "r1", "Delivered")

        invalidate_downstream("topic-a", "product-plan", "topic", tmp_path)

        product_plan = get_sessions("topic-a", "product-plan", tmp_path)
        assert all(s.state == "Delivered" for s in product_plan)
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "tech-diagnostic", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "tech-plan", tmp_path))

    def test_topic_reopen_tech_diagnostic_invalidates_tech_plan_only(self, tmp_path):
        """Topic re-open tech-diagnostic → only tech-plan Invalidated."""
        from invalidation_hook import invalidate_downstream
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "topic-a", "tech-diagnostic", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "tech-plan", "r1", "Delivered")

        invalidate_downstream("topic-a", "tech-diagnostic", "topic", tmp_path)

        tech_diag = get_sessions("topic-a", "tech-diagnostic", tmp_path)
        assert all(s.state == "Delivered" for s in tech_diag)
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "tech-plan", tmp_path))


# ---------------------------------------------------------------------------
# get_topic_doc — extended coverage
# ---------------------------------------------------------------------------

class TestTopicRefExtended:
    def _write_features_json(self, cache_dir: Path, cycle_id: str, meta: dict):
        fj = cache_dir / "features.json"
        data = {}
        if fj.exists():
            data = json.loads(fj.read_text())
        data[cycle_id] = meta
        fj.write_text(json.dumps(data), encoding="utf-8")

    def _write_topics_json(self, cache_dir: Path, topic_id: str, meta: dict):
        tj = cache_dir / "topics.json"
        data = {}
        if tj.exists():
            data = json.loads(tj.read_text())
        data[topic_id] = meta
        tj.write_text(json.dumps(data), encoding="utf-8")

    def _make_delivered_session(self, cache_dir: Path, cycle_id: str, stage: str,
                                revision: str = "r1") -> Path:
        session_dir = cache_dir / cycle_id / stage / revision
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "workflow-state.md").write_text(
            "---\ncurrent_state: Delivered\nupdated_at: 2026-06-01T00:00:00+00:00\n---\n",
            encoding="utf-8",
        )
        return session_dir

    def test_tech_work_order_maps_to_tech_plan_stage(self, tmp_path):
        """feature.tech-work-order: topic_ref_stage["tech-work-order"] == "tech-plan"
        → get_topic_doc looks in topic's tech-plan sessions and returns path."""
        from hook_guard import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "copilot", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "copilot"})
        session_dir = self._make_delivered_session(tmp_path, topic_id, "tech-plan")

        result = get_topic_doc("feat-a", "tech-work-order", tmp_path, _CONFIG_DIR)

        assert result == session_dir

    def test_tech_code_null_ref_stage_returns_none_extended(self, tmp_path):
        """feature.tech-code: topic_ref_stage["tech-code"] is null → returns None (no error)."""
        from hook_guard import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "copilot", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "copilot"})

        result = get_topic_doc("feat-a", "tech-code", tmp_path, _CONFIG_DIR)

        assert result is None

    def test_valid_topic_delivered_session_returns_path(self, tmp_path):
        """topic_id valid + corresponding stage has Delivered session → returns session path."""
        from hook_guard import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "copilot", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "copilot"})
        session_dir = self._make_delivered_session(tmp_path, topic_id, "tech-plan")

        result = get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)

        assert result == session_dir

    def test_valid_topic_no_delivered_session_returns_none_extended(self, tmp_path):
        """topic_id valid + no Delivered session in ref stage → returns None."""
        from hook_guard import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "copilot", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "copilot"})

        result = get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)

        assert result is None

    def test_topic_id_empty_field_returns_none(self, tmp_path):
        """topic_id field present but empty string → returns None, no error."""
        from hook_guard import get_topic_doc
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "copilot", "topic_id": ""})

        result = get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)

        assert result is None

    def test_topic_id_points_to_nonexistent_topic_raises_value_error(self, tmp_path):
        """topic_id not in topics.json → ValueError raised."""
        from hook_guard import get_topic_doc
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "copilot",
                                   "topic_id": "topic-does-not-exist"})
        self._write_topics_json(tmp_path, "topic-other", {"name": "t", "execution_mode": "copilot"})

        with pytest.raises(ValueError):
            get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_feature_without_topic_id_loads_normally(self, tmp_path):
        """Old features.json entry without topic_id field → loads, treated as no topic."""
        from hook_guard import get_topic_doc
        fj = tmp_path / "features.json"
        fj.write_text(json.dumps({"feat-old": {"name": "legacy", "execution_mode": "cursor"}}),
                      encoding="utf-8")

        result = get_topic_doc("feat-old", "tech-plan", tmp_path, _CONFIG_DIR)

        assert result is None

    def test_session_in_progress_state_skipped_no_error(self, tmp_path):
        """Session file with state 'InProgress' → get_sessions silently skips it."""
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "InProgress")

        sessions = get_sessions("feat-a", "tech-plan", tmp_path)

        assert sessions == []

    def test_session_ready_for_delivery_state_skipped_no_error(self, tmp_path):
        """Session file with state 'ReadyForDelivery' → get_sessions silently skips it."""
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "ReadyForDelivery")

        sessions = get_sessions("feat-a", "tech-plan", tmp_path)

        assert sessions == []
