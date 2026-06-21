#!/usr/bin/env python3
"""Tests for hook_guard gate functions: has_any_valid_session, current_effective_delivered,
check_gate, get_topic_doc."""

import json
import re
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
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
    from workflow_sessions import STAGE_FLAT, stage_subdir
    subdir = stage_subdir(stage)
    if stage in STAGE_FLAT:
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
        from workflow_sessions import has_any_valid_session
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered")
        assert has_any_valid_session("feat-a", "tech-plan", tmp_path) is True

    def test_all_invalidated_returns_false(self, tmp_path):
        from workflow_sessions import has_any_valid_session
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Invalidated")
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r2", "Invalidated")
        assert has_any_valid_session("feat-a", "tech-plan", tmp_path) is False

    def test_no_sessions_returns_false(self, tmp_path):
        from workflow_sessions import has_any_valid_session
        assert has_any_valid_session("feat-a", "tech-plan", tmp_path) is False

    def test_drafting_counts_as_valid(self, tmp_path):
        from workflow_sessions import has_any_valid_session
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Drafting")
        assert has_any_valid_session("feat-a", "tech-plan", tmp_path) is True

    def test_old_state_names_ignored(self, tmp_path):
        from workflow_sessions import has_any_valid_session
        # InProgress is not in _VALID_STATES for plan stages → skipped
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "InProgress")
        assert has_any_valid_session("feat-a", "tech-plan", tmp_path) is False

    def test_flat_stage_inprogress_counts_as_valid(self, tmp_path):
        from workflow_sessions import has_any_valid_session
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "InProgress")
        assert has_any_valid_session("feat-a", "product-diagnostic", tmp_path) is True


# ---------------------------------------------------------------------------
# current_effective_delivered
# ---------------------------------------------------------------------------

class TestCurrentEffectiveDelivered:
    def test_single_delivered_returns_true(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        assert current_effective_delivered("feat-a", "tech-plan", tmp_path) is True

    def test_latest_non_invalidated_is_drafting_returns_false(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r2", "Drafting",
                             "2026-06-02T10:00:00+00:00")
        assert current_effective_delivered("feat-a", "tech-plan", tmp_path) is False

    def test_no_valid_sessions_returns_false(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        assert current_effective_delivered("feat-a", "tech-plan", tmp_path) is False

    def test_all_invalidated_returns_false(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Invalidated")
        assert current_effective_delivered("feat-a", "tech-plan", tmp_path) is False

    def test_multiple_delivered_latest_delivered_returns_true(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r2", "Delivered",
                             "2026-06-02T10:00:00+00:00")
        assert current_effective_delivered("feat-a", "tech-plan", tmp_path) is True

    def test_flat_stage_delivered_returns_true(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "Delivered")
        assert current_effective_delivered("feat-a", "product-diagnostic", tmp_path) is True

    def test_flat_stage_inprogress_returns_false(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "InProgress")
        assert current_effective_delivered("feat-a", "product-diagnostic", tmp_path) is False


# ---------------------------------------------------------------------------
# check_gate  (uses real config files from lulu-dev-workflow/config/)
# ---------------------------------------------------------------------------

class TestCheckGate:
    """Gate uses transition-table logic backed by cycle-state.json."""

    def test_null_allows_first_stage_only(self, tmp_path):
        """No cycle-state.json: product-diagnostic (first stage) is allowed from NULL."""
        from start_gate import check_gate
        ok, msg = check_gate("feat-a", "product-diagnostic", "feature", tmp_path)
        assert ok is True
        assert msg == "OK"

    def test_null_allows_tech_diagnostic_direct_entry(self, tmp_path):
        """null → tech-diagnostic is listed in transition-table.json → allowed."""
        from start_gate import check_gate
        ok, msg = check_gate("feat-a", "tech-diagnostic", "feature", tmp_path)
        assert ok is True
        assert msg == "OK"

    def test_null_blocks_non_first_stage(self, tmp_path):
        """No cycle-state.json: product-spec is not a valid NULL entry → blocked."""
        from start_gate import check_gate
        ok, msg = check_gate("feat-a", "product-spec", "feature", tmp_path)
        assert ok is False
        assert "NULL" in msg or "product-diagnostic" in msg or "tech-diagnostic" in msg
        assert "STOP" in msg
        assert "start.py" in msg

    def test_gap_scenario_blocked_by_transition_table(self, tmp_path):
        """current=product-spec, Delivered: jumping to tech-plan (skipping tech-diagnostic) → blocked."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "product-spec")
        _make_workflow_state(tmp_path, "feat-a", "product-spec", "r1", "Delivered")
        ok, msg = check_gate("feat-a", "tech-plan", "feature", tmp_path)
        assert ok is False
        assert "product-spec" in msg or "tech-diagnostic" in msg
        assert "STOP" in msg

    def test_tech_plan_to_tech_design_blocked_with_stop(self, tmp_path):
        """current=tech-plan: tech-design is not a valid advance → blocked with STOP."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "tech-plan")
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered")
        ok, msg = check_gate("feat-a", "tech-design", "feature", tmp_path)
        assert ok is False
        assert "Invalid transition" in msg
        assert "tech-work-order" in msg
        assert "STOP" in msg

    def test_valid_advance_after_delivery(self, tmp_path):
        """current=product-diagnostic (Delivered): advance to product-spec → allowed."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "product-diagnostic")
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "Delivered")
        ok, msg = check_gate("feat-a", "product-spec", "feature", tmp_path)
        assert ok is True
        assert msg == "OK"

    def test_advance_blocked_if_not_delivered(self, tmp_path):
        """current=product-diagnostic (InProgress): advance to product-spec → blocked."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "product-diagnostic")
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "InProgress")
        ok, msg = check_gate("feat-a", "product-spec", "feature", tmp_path)
        assert ok is False
        assert "product-diagnostic" in msg
        assert "STOP" in msg
        assert "Gate blocked:" not in msg

    def test_reentry_always_allowed(self, tmp_path):
        """Re-entering the current stage is always allowed (no session required)."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "product-spec")
        ok, msg = check_gate("feat-a", "product-spec", "feature", tmp_path)
        assert ok is True

    def test_stage_not_in_cycle_always_allowed(self, tmp_path):
        """'diagnostic' is not in the feature cycle stages → gate always OK."""
        from start_gate import check_gate
        ok, msg = check_gate("feat-a", "diagnostic", "feature", tmp_path)
        assert ok is True

    def test_topic_cycle_valid_advance(self, tmp_path):
        """Topic cycle: current=product-diagnostic (Delivered) → product-arch allowed."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "topic-a", "product-diagnostic")
        _make_workflow_state(tmp_path, "topic-a", "product-diagnostic", "r1", "Delivered")
        ok, msg = check_gate("topic-a", "product-arch", "topic", tmp_path)
        assert ok is True

    def test_stale_cycle_state_treated_as_null(self, tmp_path):
        """cycle-state.json with a stage not in the cycle → treated as NULL."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "some-unknown-stage")
        ok, msg = check_gate("feat-a", "product-diagnostic", "feature", tmp_path)
        assert ok is True  # NULL → first stage allowed

    def test_full_feature_cycle_sequence(self, tmp_path):
        """Walk through all feature cycle stages in order; each advance requires Delivered."""
        from start_gate import check_gate
        stages = ["product-diagnostic", "product-spec", "tech-diagnostic",
                  "tech-plan", "tech-work-order", "tech-code"]
        for i, stage in enumerate(stages):
            if i == 0:
                ok, _ = check_gate("feat-a", stage, "feature", tmp_path)
                assert ok is True, f"First stage {stage} should be allowed from NULL"
                _make_workflow_state(tmp_path, "feat-a", stage, "r1", "Delivered")
                _make_cycle_state(tmp_path, "feat-a", stage)
            else:
                ok, _ = check_gate("feat-a", stage, "feature", tmp_path)
                assert ok is True, f"Stage {stage} should be allowed after prior Delivered"
                _make_workflow_state(tmp_path, "feat-a", stage, "r1", "Delivered")
                _make_cycle_state(tmp_path, "feat-a", stage)


# ---------------------------------------------------------------------------
# get_sessions — unit
# ---------------------------------------------------------------------------

class TestGetSessions:
    def test_returns_empty_when_no_sessions(self, tmp_path):
        from workflow_sessions import get_sessions
        sessions = get_sessions("feat-a", "tech-plan", tmp_path)
        assert sessions == []

    def test_old_state_names_skipped_for_plan_stage(self, tmp_path):
        from workflow_sessions import get_sessions
        # InProgress is not in _VALID_STATES for plan stages → skipped
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "InProgress")
        sessions = get_sessions("feat-a", "tech-plan", tmp_path)
        assert sessions == []

    def test_returns_session_info_objects(self, tmp_path):
        from workflow_sessions import SessionInfo, get_sessions
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        sessions = get_sessions("feat-a", "tech-plan", tmp_path)
        assert len(sessions) == 1
        assert isinstance(sessions[0], SessionInfo)
        assert sessions[0].state == "Delivered"
        assert sessions[0].revision == "revision1"

    def test_flat_stage_inprogress_returned(self, tmp_path):
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "InProgress")
        sessions = get_sessions("feat-a", "product-diagnostic", tmp_path)
        assert len(sessions) == 1
        assert sessions[0].state == "InProgress"
        assert sessions[0].revision == "r0"

    def test_flat_stage_delivered_returned(self, tmp_path):
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "product-diagnostic", "r1", "Delivered")
        sessions = get_sessions("feat-a", "product-diagnostic", tmp_path)
        assert len(sessions) == 1
        assert sessions[0].state == "Delivered"

    def test_session_has_state_path(self, tmp_path):
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered")
        sessions = get_sessions("feat-a", "tech-plan", tmp_path)
        assert sessions[0].state_path is not None
        assert sessions[0].state_path.exists()

    def test_multiple_revisions_returned(self, tmp_path):
        from workflow_sessions import get_sessions
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
        from start_gate import get_topic_doc
        self._write_features_json(tmp_path, "feat-a", {"name": "x", "execution_mode": "guided"})
        result = get_topic_doc("feat-a", "tech-plan", tmp_path)
        assert result is None

    def test_invalid_topic_id_raises_value_error(self, tmp_path):
        from start_gate import get_topic_doc
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided",
                                   "topic_id": "topic-20260101000000-deadbeef"})
        # cycles.json does not exist → ValueError
        with pytest.raises(ValueError):
            get_topic_doc("feat-a", "tech-plan", tmp_path)

    def test_tech_code_unmapped_returns_none(self, tmp_path):
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided",
                                   "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})
        # tech-code not in topic_doc_stage
        result = get_topic_doc("feat-a", "tech-code", tmp_path)
        assert result is None

    def test_valid_topic_no_delivered_session_returns_none(self, tmp_path):
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided",
                                   "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})
        # No session files → None
        result = get_topic_doc("feat-a", "tech-plan", tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# invalidate_downstream
# ---------------------------------------------------------------------------

class TestInvalidateDownstream:
    def test_reopen_product_spec_invalidates_downstream(self, tmp_path):
        """Re-opening product-spec: all downstream stages become Invalidated."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "product-spec", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-diagnostic", "r1", "InProgress")
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-work-order", "r1", "Drafting")

        invalidate_downstream("feat-a", "product-spec", "feature", tmp_path)

        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "tech-diagnostic", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "tech-plan", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "tech-work-order", tmp_path))

    def test_backfill_product_diagnostic_invalidates_product_spec_and_later(self, tmp_path):
        """Back-fill: re-open product-diagnostic → product-spec and all later stages Invalidated."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "product-spec", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-diagnostic", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "Delivered")

        invalidate_downstream("feat-a", "product-diagnostic", "feature", tmp_path)

        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "product-spec", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "tech-diagnostic", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "tech-plan", tmp_path))

    def test_from_stage_itself_not_modified(self, tmp_path):
        """from_stage sessions are NOT touched by invalidate_downstream."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "product-spec", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-diagnostic", "r1", "InProgress")

        invalidate_downstream("feat-a", "product-spec", "feature", tmp_path)

        product_spec = get_sessions("feat-a", "product-spec", tmp_path)
        assert len(product_spec) == 1
        assert product_spec[0].state == "Delivered"

    def test_already_invalidated_stays_invalidated_idempotent(self, tmp_path):
        """Idempotent: already-Invalidated session stays Invalidated, no error on repeat call."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "product-spec", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-diagnostic", "r1", "Invalidated")

        invalidate_downstream("feat-a", "product-spec", "feature", tmp_path)
        invalidate_downstream("feat-a", "product-spec", "feature", tmp_path)

        tech_diag = get_sessions("feat-a", "tech-diagnostic", tmp_path)
        assert all(s.state == "Invalidated" for s in tech_diag)

    def test_old_state_names_not_modified(self, tmp_path):
        """Sessions with old state names (InProgress in a plan-stage file) are skipped — unchanged."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import stage_subdir
        # Create tech-plan session with "InProgress" (not in _VALID_STATES for plan stages)
        session_dir = tmp_path / "feat-a" / stage_subdir("tech-plan") / "revision1"
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "workflow-state.md"
        ws.write_text("---\ncurrent_state: InProgress\n---\n", encoding="utf-8")

        invalidate_downstream("feat-a", "product-spec", "feature", tmp_path)

        assert "InProgress" in ws.read_text()


# ---------------------------------------------------------------------------
# Cross-container isolation
# ---------------------------------------------------------------------------

class TestCrossContainerIsolation:
    def test_topic_reopen_does_not_affect_feature_container(self, tmp_path):
        """Re-opening a topic container leaves feature container sessions untouched."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "topic-a", "product-diagnostic", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "product-arch", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "product-spec", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "tech-diagnostic", "r1", "Delivered")

        invalidate_downstream("topic-a", "product-diagnostic", "topic", tmp_path)

        feat_spec = get_sessions("feat-a", "product-spec", tmp_path)
        feat_diag = get_sessions("feat-a", "tech-diagnostic", tmp_path)
        assert all(s.state == "Delivered" for s in feat_spec)
        assert all(s.state == "Delivered" for s in feat_diag)

    def test_topic_reopen_product_diagnostic_invalidates_all_later(self, tmp_path):
        """Topic re-open product-diagnostic → product-arch, tech-diagnostic, tech-arch Invalidated."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "topic-a", "product-arch", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "tech-diagnostic", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "tech-arch", "r1", "Delivered")

        invalidate_downstream("topic-a", "product-diagnostic", "topic", tmp_path)

        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "product-arch", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "tech-diagnostic", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "tech-arch", tmp_path))

    def test_topic_reopen_product_arch_invalidates_tech(self, tmp_path):
        """Topic re-open product-arch → tech-diagnostic, tech-arch Invalidated; product-arch unchanged."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "topic-a", "product-arch", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "tech-diagnostic", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "tech-arch", "r1", "Delivered")

        invalidate_downstream("topic-a", "product-arch", "topic", tmp_path)

        product_arch = get_sessions("topic-a", "product-arch", tmp_path)
        assert all(s.state == "Delivered" for s in product_arch)
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "tech-diagnostic", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "tech-arch", tmp_path))

    def test_topic_reopen_tech_diagnostic_invalidates_tech_arch(self, tmp_path):
        """Topic re-open tech-diagnostic → tech-arch Invalidated."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "topic-a", "tech-diagnostic", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "tech-arch", "r1", "Delivered")

        invalidate_downstream("topic-a", "tech-diagnostic", "topic", tmp_path)

        tech_diag = get_sessions("topic-a", "tech-diagnostic", tmp_path)
        assert all(s.state == "Delivered" for s in tech_diag)
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "tech-arch", tmp_path))


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
        from workflow_sessions import STAGE_FLAT, stage_subdir
        subdir = stage_subdir(stage)
        if stage in STAGE_FLAT:
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

    def test_tech_design_maps_to_tech_arch_stage(self, tmp_path):
        """feature.tech-design: topic_doc_stage maps to tech-arch → get_topic_doc returns path."""
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})
        session_dir = self._make_delivered_session(tmp_path, topic_id, "tech-arch")

        result = get_topic_doc("feat-a", "tech-design", tmp_path)

        assert result == session_dir

    def test_tech_plan_unmapped_returns_none(self, tmp_path):
        """feature.tech-plan: not in topic_doc_stage → returns None."""
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})
        self._make_delivered_session(tmp_path, topic_id, "tech-arch")

        result = get_topic_doc("feat-a", "tech-plan", tmp_path)

        assert result is None

    def test_tech_code_unmapped_returns_none_extended(self, tmp_path):
        """feature.tech-code: not in topic_doc_stage → returns None (no error)."""
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})

        result = get_topic_doc("feat-a", "tech-code", tmp_path)

        assert result is None

    def test_product_spec_maps_to_product_arch(self, tmp_path):
        """feature.product-spec: topic_doc_stage maps to product-arch → returns session path."""
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})
        session_dir = self._make_delivered_session(tmp_path, topic_id, "product-arch")

        result = get_topic_doc("feat-a", "product-spec", tmp_path)

        assert result == session_dir

    def test_valid_topic_no_delivered_session_returns_none_extended(self, tmp_path):
        """topic_id valid + no Delivered session in ref stage → returns None."""
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t", "execution_mode": "guided"})

        result = get_topic_doc("feat-a", "tech-plan", tmp_path)

        assert result is None

    def test_topic_id_empty_field_returns_none(self, tmp_path):
        """topic_id field present but empty string → returns None, no error."""
        from start_gate import get_topic_doc
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided", "topic_id": ""})

        result = get_topic_doc("feat-a", "tech-plan", tmp_path)

        assert result is None

    def test_topic_id_points_to_nonexistent_topic_raises_value_error(self, tmp_path):
        """topic_id not in cycles.json → ValueError raised."""
        from start_gate import get_topic_doc
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "execution_mode": "guided",
                                   "topic_id": "topic-does-not-exist"})
        self._write_topics_json(tmp_path, "topic-other", {"name": "t", "execution_mode": "guided"})

        with pytest.raises(ValueError):
            get_topic_doc("feat-a", "tech-plan", tmp_path)


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_feature_without_topic_id_loads_normally(self, tmp_path):
        """Old cycles.json entry without topic_id field → loads, treated as no topic."""
        from start_gate import get_topic_doc
        fj = tmp_path / "cycles.json"
        fj.write_text(json.dumps({"feat-old": {"name": "legacy", "execution_mode": "cursor"}}),
                      encoding="utf-8")

        result = get_topic_doc("feat-old", "tech-plan", tmp_path)

        assert result is None

    def test_session_in_progress_state_skipped_no_error(self, tmp_path):
        """Session file with state 'InProgress' in a plan stage → get_sessions silently skips it."""
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "InProgress")

        sessions = get_sessions("feat-a", "tech-plan", tmp_path)

        assert sessions == []

    def test_session_ready_for_delivery_state_skipped_no_error(self, tmp_path):
        """Session file with state 'ReadyForDelivery' → get_sessions silently skips it."""
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "tech-plan", "r1", "ReadyForDelivery")

        sessions = get_sessions("feat-a", "tech-plan", tmp_path)

        assert sessions == []
