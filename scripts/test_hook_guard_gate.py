#!/usr/bin/env python3
"""Tests for hook_guard gate functions: has_any_valid_session, current_effective_delivered,
check_gate, get_topic_doc."""

import json
import re
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
    """Create a session state file at the correct path for the given stage.

    Flat stages (product-diagnostic, tech-diagnostic, diagnostic) → session-state.md.
    Plan stages → revision{N}/workflow-state.md.
    """
    from hook_guard import _stage_subdir, _STAGE_FLAT
    subdir = _stage_subdir(stage)
    if stage in _STAGE_FLAT:
        session_dir = tmp_path / cycle_id / subdir
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "session-state.md"
    else:
        rev_name = (
            f"revision{revision.lstrip('r')}"
            if re.match(r"^r\d+$", revision)
            else revision
        )
        session_dir = tmp_path / cycle_id / subdir / rev_name
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "workflow-state.md"
    ws.write_text(
        f"---\ncurrent_state: {state}\nupdated_at: {updated_at}\n---\n",
        encoding="utf-8",
    )
    return ws


def _make_cycle_state(tmp_path: Path, cycle_id: str, stage: str) -> Path:
    """Create cycle-state.json for check_gate transition-table tests."""
    p = tmp_path / cycle_id / "cycle-state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"current_stage": stage, "updated_at": "2026-06-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    return p


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
        # InProgress is not in _VALID_STATES for plan stages → skipped
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "InProgress")
        assert has_any_valid_session("feat-a", "tech-plan", tmp_path) is False

    def test_flat_stage_inprogress_counts_as_valid(self, tmp_path):
        from hook_guard import has_any_valid_session
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "InProgress")
        assert has_any_valid_session("feat-a", "product-diagnostic", tmp_path) is True


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

    def test_flat_stage_delivered_returns_true(self, tmp_path):
        from hook_guard import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "Delivered")
        assert current_effective_delivered("feat-a", "product-diagnostic", tmp_path) is True

    def test_flat_stage_inprogress_returns_false(self, tmp_path):
        from hook_guard import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "InProgress")
        assert current_effective_delivered("feat-a", "product-diagnostic", tmp_path) is False


# ---------------------------------------------------------------------------
# check_gate  (uses real config files from lulu-dev-workflow/config/)
# ---------------------------------------------------------------------------

class TestCheckGate:
    """Gate uses transition-table logic backed by cycle-state.json."""

    def test_null_allows_first_stage_only(self, tmp_path):
        """No cycle-state.json: only the first stage (product-diagnostic) is valid."""
        from hook_guard import check_gate
        ok, msg = check_gate("feat-a", "product-diagnostic", "feature", tmp_path, _CONFIG_DIR)
        assert ok is True
        assert msg == "OK"

    def test_null_blocks_non_first_stage(self, tmp_path):
        """No cycle-state.json: product-plan is not the first stage → blocked."""
        from hook_guard import check_gate
        ok, msg = check_gate("feat-a", "product-plan", "feature", tmp_path, _CONFIG_DIR)
        assert ok is False
        assert "NULL" in msg or "product-diagnostic" in msg

    def test_gap_scenario_blocked_by_transition_table(self, tmp_path):
        """current=product-plan, Delivered: jumping to tech-plan (skipping tech-diagnostic) → blocked."""
        from hook_guard import check_gate
        _make_cycle_state(tmp_path, "feat-a", "product-plan")
        _make_workflow_state(tmp_path, "feat-a", "product-plan", "r1", "Delivered")
        ok, msg = check_gate("feat-a", "tech-plan", "feature", tmp_path, _CONFIG_DIR)
        assert ok is False
        assert "product-plan" in msg or "tech-diagnostic" in msg

    def test_valid_advance_after_delivery(self, tmp_path):
        """current=product-diagnostic (Delivered): advance to product-plan → allowed."""
        from hook_guard import check_gate
        _make_cycle_state(tmp_path, "feat-a", "product-diagnostic")
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "Delivered")
        ok, msg = check_gate("feat-a", "product-plan", "feature", tmp_path, _CONFIG_DIR)
        assert ok is True
        assert msg == "OK"

    def test_advance_blocked_if_not_delivered(self, tmp_path):
        """current=product-diagnostic (InProgress): advance to product-plan → blocked."""
        from hook_guard import check_gate
        _make_cycle_state(tmp_path, "feat-a", "product-diagnostic")
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "InProgress")
        ok, msg = check_gate("feat-a", "product-plan", "feature", tmp_path, _CONFIG_DIR)
        assert ok is False
        assert "product-diagnostic" in msg

    def test_reentry_always_allowed(self, tmp_path):
        """Re-entering the current stage is always allowed (no session required)."""
        from hook_guard import check_gate
        _make_cycle_state(tmp_path, "feat-a", "product-plan")
        ok, msg = check_gate("feat-a", "product-plan", "feature", tmp_path, _CONFIG_DIR)
        assert ok is True

    def test_stage_not_in_cycle_always_allowed(self, tmp_path):
        """'diagnostic' is not in the feature cycle stages → gate always OK."""
        from hook_guard import check_gate
        ok, msg = check_gate("feat-a", "diagnostic", "feature", tmp_path, _CONFIG_DIR)
        assert ok is True

    def test_topic_cycle_valid_advance(self, tmp_path):
        """Topic cycle: current=product-diagnostic (Delivered) → product-plan allowed."""
        from hook_guard import check_gate
        _make_cycle_state(tmp_path, "topic-a", "product-diagnostic")
        _make_workflow_state(tmp_path, "topic-a", "product-diagnostic", "r1", "Delivered")
        ok, msg = check_gate("topic-a", "product-plan", "topic", tmp_path, _CONFIG_DIR)
        assert ok is True

    def test_stale_cycle_state_treated_as_null(self, tmp_path):
        """cycle-state.json with a stage not in the cycle → treated as NULL."""
        from hook_guard import check_gate
        _make_cycle_state(tmp_path, "feat-a", "some-unknown-stage")
        ok, msg = check_gate("feat-a", "product-diagnostic", "feature", tmp_path, _CONFIG_DIR)
        assert ok is True  # NULL → first stage allowed

    def test_full_feature_cycle_sequence(self, tmp_path):
        """Walk through all feature cycle stages in order; each advance requires Delivered."""
        from hook_guard import check_gate
        stages = ["product-diagnostic", "product-plan", "tech-diagnostic",
                  "tech-plan", "tech-work-order", "tech-code"]
        for i, stage in enumerate(stages):
            if i == 0:
                ok, _ = check_gate("feat-a", stage, "feature", tmp_path, _CONFIG_DIR)
                assert ok is True, f"First stage {stage} should be allowed from NULL"
                _make_workflow_state(tmp_path, "feat-a", stage, "r1", "Delivered")
                _make_cycle_state(tmp_path, "feat-a", stage)
            else:
                ok, _ = check_gate("feat-a", stage, "feature", tmp_path, _CONFIG_DIR)
                assert ok is True, f"Stage {stage} should be allowed after prior Delivered"
                _make_workflow_state(tmp_path, "feat-a", stage, "r1", "Delivered")
                _make_cycle_state(tmp_path, "feat-a", stage)


# ---------------------------------------------------------------------------
# get_sessions — unit
# ---------------------------------------------------------------------------

class TestGetSessions:
    def test_returns_empty_when_no_sessions(self, tmp_path):
        from hook_guard import get_sessions
        sessions = get_sessions("feat-a", "tech-plan", tmp_path)
        assert sessions == []

    def test_old_state_names_skipped_for_plan_stage(self, tmp_path):
        from hook_guard import get_sessions
        # InProgress is not in _VALID_STATES for plan stages → skipped
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
        assert sessions[0].revision == "revision1"

    def test_flat_stage_inprogress_returned(self, tmp_path):
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "InProgress")
        sessions = get_sessions("feat-a", "product-diagnostic", tmp_path)
        assert len(sessions) == 1
        assert sessions[0].state == "InProgress"
        assert sessions[0].revision == "r0"

    def test_flat_stage_delivered_returned(self, tmp_path):
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "Delivered")
        sessions = get_sessions("feat-a", "product-diagnostic", tmp_path)
        assert len(sessions) == 1
        assert sessions[0].state == "Delivered"

    def test_session_has_state_path(self, tmp_path):
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered")
        sessions = get_sessions("feat-a", "tech-plan", tmp_path)
        assert sessions[0].state_path is not None
        assert sessions[0].state_path.exists()

    def test_multiple_revisions_returned(self, tmp_path):
        from hook_guard import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r2", "Drafting",
                             "2026-06-02T10:00:00+00:00")
        sessions = get_sessions("feat-a", "tech-plan", tmp_path)
        assert len(sessions) == 2
        revisions = {s.revision for s in sessions}
        assert revisions == {"revision1", "revision2"}


# ---------------------------------------------------------------------------
# get_topic_doc
# ---------------------------------------------------------------------------

class TestGetTopicDoc:
    def _write_features_json(self, cache_dir: Path, cycle_id: str, meta: dict):
        fj = cache_dir / "cycles.json"
        data = {}
        if fj.exists():
            data = json.loads(fj.read_text())
        data[cycle_id] = meta
        fj.write_text(json.dumps(data), encoding="utf-8")

    def _write_topics_json(self, cache_dir: Path, topic_id: str, meta: dict):
        tj = cache_dir / "cycles.json"
        data = {}
        if tj.exists():
            data = json.loads(tj.read_text())
        data[topic_id] = meta
        tj.write_text(json.dumps(data), encoding="utf-8")

    def test_no_topic_id_returns_none(self, tmp_path):
        from hook_guard import get_topic_doc
        self._write_features_json(tmp_path, "feat-a", {"name": "x", "execution_mode": "guided"})
        result = get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)
        assert result is None

    def test_invalid_topic_id_raises_value_error(self, tmp_path):
        from hook_guard import get_topic_doc
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided",
                                   "topic_id": "topic-20260101000000-deadbeef"})
        # cycles.json does not exist → ValueError
        with pytest.raises(ValueError):
            get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)

    def test_tech_code_null_ref_stage_returns_none(self, tmp_path):
        from hook_guard import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided",
                                   "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})
        # tech-code maps to null in topic_doc_stage
        result = get_topic_doc("feat-a", "tech-code", tmp_path, _CONFIG_DIR)
        assert result is None

    def test_valid_topic_no_delivered_session_returns_none(self, tmp_path):
        from hook_guard import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided",
                                   "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})
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
        _make_workflow_state(tmp_path, "feat-a", "tech-diagnostic", "r1", "InProgress")
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
        _make_workflow_state(tmp_path, "feat-a", "tech-diagnostic", "r1", "InProgress")

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
        """Sessions with old state names (InProgress in a plan-stage file) are skipped — unchanged."""
        from invalidation_hook import invalidate_downstream
        from hook_guard import _stage_subdir
        # Create tech-plan session with "InProgress" (not in _VALID_STATES for plan stages)
        session_dir = tmp_path / "feat-a" / _stage_subdir("tech-plan") / "revision1"
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
        fj = cache_dir / "cycles.json"
        data = {}
        if fj.exists():
            data = json.loads(fj.read_text())
        data[cycle_id] = meta
        fj.write_text(json.dumps(data), encoding="utf-8")

    def _write_topics_json(self, cache_dir: Path, topic_id: str, meta: dict):
        tj = cache_dir / "cycles.json"
        data = {}
        if tj.exists():
            data = json.loads(tj.read_text())
        data[topic_id] = meta
        tj.write_text(json.dumps(data), encoding="utf-8")

    def _make_delivered_session(self, cache_dir: Path, cycle_id: str, stage: str,
                                revision: str = "r1") -> Path:
        from hook_guard import _stage_subdir, _STAGE_FLAT
        subdir = _stage_subdir(stage)
        if stage in _STAGE_FLAT:
            session_dir = cache_dir / cycle_id / subdir
            session_dir.mkdir(parents=True, exist_ok=True)
            (session_dir / "session-state.md").write_text(
                "---\ncurrent_state: Delivered\nupdated_at: 2026-06-01T00:00:00+00:00\n---\n",
                encoding="utf-8",
            )
        else:
            rev_name = (
                f"revision{revision.lstrip('r')}"
                if re.match(r"^r\d+$", revision)
                else revision
            )
            session_dir = cache_dir / cycle_id / subdir / rev_name
            session_dir.mkdir(parents=True, exist_ok=True)
            (session_dir / "workflow-state.md").write_text(
                "---\ncurrent_state: Delivered\nupdated_at: 2026-06-01T00:00:00+00:00\n---\n",
                encoding="utf-8",
            )
        return session_dir

    def test_tech_work_order_maps_to_tech_plan_stage(self, tmp_path):
        """feature.tech-work-order: topic_doc_stage["tech-work-order"] == "tech-plan"
        → get_topic_doc looks in topic's tech-plan sessions and returns path."""
        from hook_guard import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})
        session_dir = self._make_delivered_session(tmp_path, topic_id, "tech-plan")

        result = get_topic_doc("feat-a", "tech-work-order", tmp_path, _CONFIG_DIR)

        assert result == session_dir

    def test_tech_code_null_ref_stage_returns_none_extended(self, tmp_path):
        """feature.tech-code: topic_doc_stage["tech-code"] is null → returns None (no error)."""
        from hook_guard import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})

        result = get_topic_doc("feat-a", "tech-code", tmp_path, _CONFIG_DIR)

        assert result is None

    def test_valid_topic_delivered_session_returns_path(self, tmp_path):
        """topic_id valid + corresponding stage has Delivered session → returns session path."""
        from hook_guard import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})
        session_dir = self._make_delivered_session(tmp_path, topic_id, "tech-plan")

        result = get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)

        assert result == session_dir

    def test_valid_topic_no_delivered_session_returns_none_extended(self, tmp_path):
        """topic_id valid + no Delivered session in ref stage → returns None."""
        from hook_guard import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})

        result = get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)

        assert result is None

    def test_topic_id_empty_field_returns_none(self, tmp_path):
        """topic_id field present but empty string → returns None, no error."""
        from hook_guard import get_topic_doc
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided", "topic_id": ""})

        result = get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)

        assert result is None

    def test_topic_id_points_to_nonexistent_topic_raises_value_error(self, tmp_path):
        """topic_id not in cycles.json → ValueError raised."""
        from hook_guard import get_topic_doc
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided",
                                   "topic_id": "topic-does-not-exist"})
        self._write_topics_json(tmp_path, "topic-other", {"name": "t", "execution_mode": "guided"})

        with pytest.raises(ValueError):
            get_topic_doc("feat-a", "tech-plan", tmp_path, _CONFIG_DIR)


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_feature_without_topic_id_loads_normally(self, tmp_path):
        """Old cycles.json entry without topic_id field → loads, treated as no topic."""
        from hook_guard import get_topic_doc
        fj = tmp_path / "cycles.json"
        fj.write_text(json.dumps({"feat-old": {"name": "legacy", "execution_mode": "cursor"}}),
                      encoding="utf-8")

        result = get_topic_doc("feat-old", "tech-plan", tmp_path, _CONFIG_DIR)

        assert result is None

    def test_session_in_progress_state_skipped_no_error(self, tmp_path):
        """Session file with state 'InProgress' in a plan stage → get_sessions silently skips it."""
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
