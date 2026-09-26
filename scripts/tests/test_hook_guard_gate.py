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


_COMPOSE_STAGES = frozenset(
    {"lulu-arch", "lulu-blueprint", "lulu-design", "lulu-plan", "lulu-spec"}
)


def _make_workflow_state(tmp_path: Path, cycle_id: str, stage: str, revision: str,
                          state: str, updated_at: str = "2026-06-01T00:00:00+00:00") -> Path:
    """Create a session state file at the correct path for the given stage.

    Flat stages (lulu-bet, lulu-approach, diagnostic) → session-state.md.
    Compose stages → session-state.md v2 + revision{N}/workflow-state.md.
    Other plan-like stages → revision{N}/workflow-state.md.
    """
    from workflow_sessions import STAGE_FLAT, stage_subdir
    subdir = stage_subdir(stage)
    if stage in STAGE_FLAT:
        session_dir = tmp_path / cycle_id / subdir
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "session-state.md"
        ws.write_text(
            f"---\ncurrent_state: {state}\nupdated_at: {updated_at}\n---\n",
            encoding="utf-8",
        )
        return ws
    rev_name = (
        f"revision{revision.lstrip('r')}"
        if re.match(r"^r\d+$", revision)
        else revision
    )
    session_dir = tmp_path / cycle_id / subdir / rev_name
    session_dir.mkdir(parents=True, exist_ok=True)
    ws = session_dir / "workflow-state.md"
    if stage in _COMPOSE_STAGES:
        active_doc = int(re.sub(r"\D", "", rev_name) or "1")
        ss = tmp_path / cycle_id / subdir / "session-state.md"
        if not ss.is_file():
            ss.write_text(
                "---\n"
                "version: 2\n"
                f"active_doc: {active_doc}\n"
                "profile_path: /tmp/compose-profile.json\n"
                f"profile_digest: {'a' * 64}\n"
                "start_id: test-start\n"
                "holder_finalized: true\n"
                f"updated_at: {updated_at}\n"
                "---\n",
                encoding="utf-8",
            )
        mode = "product" if stage == "lulu-spec" else "tech"
        cycle_type = "topic" if cycle_id.startswith("topic") else "feature"
        ws.write_text(
            "---\n"
            "version: 1\n"
            "workflow: tech-doc\n"
            f"mode: {mode}\n"
            f"cycle_type: {cycle_type}\n"
            f"current_state: {state}\n"
            "evaluate_round: 0\n"
            f"updated_at: {updated_at}\n"
            "---\n",
            encoding="utf-8",
        )
        return ws
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
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Delivered")
        assert has_any_valid_session("feat-a", "lulu-plan", tmp_path) is True

    def test_all_invalidated_returns_false(self, tmp_path):
        from workflow_sessions import has_any_valid_session
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Invalidated")
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r2", "Invalidated")
        assert has_any_valid_session("feat-a", "lulu-plan", tmp_path) is False

    def test_no_sessions_returns_false(self, tmp_path):
        from workflow_sessions import has_any_valid_session
        assert has_any_valid_session("feat-a", "lulu-plan", tmp_path) is False

    def test_drafting_counts_as_valid(self, tmp_path):
        from workflow_sessions import has_any_valid_session
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Working")
        assert has_any_valid_session("feat-a", "lulu-plan", tmp_path) is True

    def test_old_state_names_ignored(self, tmp_path):
        from workflow_sessions import has_any_valid_session
        # InProgress is not in _VALID_STATES for plan stages → skipped
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "InProgress")
        assert has_any_valid_session("feat-a", "lulu-plan", tmp_path) is False

    def test_flat_stage_inprogress_counts_as_valid(self, tmp_path):
        from workflow_sessions import has_any_valid_session
        _make_workflow_state(tmp_path, "feat-a", "lulu-bet", "r1", "InProgress")
        assert has_any_valid_session("feat-a", "lulu-bet", tmp_path) is True


# ---------------------------------------------------------------------------
# current_effective_delivered
# ---------------------------------------------------------------------------

class TestCurrentEffectiveDelivered:
    def test_single_delivered_returns_true(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        assert current_effective_delivered("feat-a", "lulu-plan", tmp_path) is True

    def test_latest_non_invalidated_is_drafting_returns_false(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r2", "Working",
                             "2026-06-02T10:00:00+00:00")
        assert current_effective_delivered("feat-a", "lulu-plan", tmp_path) is False

    def test_no_valid_sessions_returns_false(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        assert current_effective_delivered("feat-a", "lulu-plan", tmp_path) is False

    def test_all_invalidated_returns_false(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Invalidated")
        assert current_effective_delivered("feat-a", "lulu-plan", tmp_path) is False

    def test_multiple_delivered_latest_delivered_returns_true(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r2", "Delivered",
                             "2026-06-02T10:00:00+00:00")
        assert current_effective_delivered("feat-a", "lulu-plan", tmp_path) is True

    def test_flat_stage_delivered_returns_true(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "lulu-bet", "r1", "Delivered")
        assert current_effective_delivered("feat-a", "lulu-bet", tmp_path) is True

    def test_flat_stage_inprogress_returns_false(self, tmp_path):
        from workflow_sessions import current_effective_delivered
        _make_workflow_state(tmp_path, "feat-a", "lulu-bet", "r1", "InProgress")
        assert current_effective_delivered("feat-a", "lulu-bet", tmp_path) is False


# ---------------------------------------------------------------------------
# check_gate  (uses real config files from lulu-dev-workflow/config/)
# ---------------------------------------------------------------------------

class TestCheckGate:
    """Gate uses transition-table logic backed by cycle-state.json."""

    def test_null_allows_first_stage_only(self, tmp_path):
        """No cycle-state.json: lulu-bet (first stage) is allowed from NULL."""
        from start_gate import check_gate
        ok, msg = check_gate("feat-a", "lulu-bet", "feature", tmp_path)
        assert ok is True
        assert msg == "OK"

    def test_null_allows_tech_diagnostic_direct_entry(self, tmp_path):
        """null → lulu-approach is listed in transition-table.json → allowed."""
        from start_gate import check_gate
        ok, msg = check_gate("feat-a", "lulu-approach", "feature", tmp_path)
        assert ok is True
        assert msg == "OK"

    def test_null_blocks_non_first_stage(self, tmp_path):
        """No cycle-state.json: lulu-spec is not a valid NULL entry → blocked."""
        from start_gate import check_gate
        ok, msg = check_gate("feat-a", "lulu-spec", "feature", tmp_path)
        assert ok is False
        assert "NULL" in msg or "lulu-bet" in msg or "lulu-approach" in msg
        assert "STOP" in msg
        assert "start.py" in msg

    def test_gap_scenario_blocked_by_transition_table(self, tmp_path):
        """current=lulu-spec, Delivered: jumping to lulu-plan (skipping lulu-approach) → blocked."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "lulu-spec")
        _make_workflow_state(tmp_path, "feat-a", "lulu-spec", "r1", "Delivered")
        ok, msg = check_gate("feat-a", "lulu-plan", "feature", tmp_path)
        assert ok is False
        assert "lulu-spec" in msg or "lulu-approach" in msg
        assert "STOP" in msg

    def test_tech_plan_to_tech_design_blocked_with_stop(self, tmp_path):
        """current=lulu-plan: lulu-design is not a valid advance → blocked with STOP."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "lulu-plan")
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Delivered")
        ok, msg = check_gate("feat-a", "lulu-design", "feature", tmp_path)
        assert ok is False
        assert "Invalid transition" in msg
        assert "lulu-tasks" in msg
        assert "STOP" in msg

    def test_valid_advance_after_delivery(self, tmp_path):
        """current=lulu-bet (Delivered): advance to lulu-spec → allowed."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "lulu-bet")
        _make_workflow_state(tmp_path, "feat-a", "lulu-bet", "r1", "Delivered")
        ok, msg = check_gate("feat-a", "lulu-spec", "feature", tmp_path)
        assert ok is True
        assert msg == "OK"

    def test_compose_flat_path_design_to_plan(self, tmp_path):
        """current=lulu-design (Delivered at lulu-design/revision1/): advance to lulu-plan."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "lulu-design")
        _make_workflow_state(tmp_path, "feat-a", "lulu-design", "r1", "Delivered")
        flat_ws = tmp_path / "feat-a" / "lulu-design" / "revision1" / "workflow-state.md"
        assert flat_ws.exists()
        assert not (tmp_path / "feat-a" / "lulu" / "design").exists()
        ok, msg = check_gate("feat-a", "lulu-plan", "feature", tmp_path)
        assert ok is True
        assert msg == "OK"

    def test_advance_blocked_if_not_delivered(self, tmp_path):
        """current=lulu-bet (InProgress): advance to lulu-spec → blocked."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "lulu-bet")
        _make_workflow_state(tmp_path, "feat-a", "lulu-bet", "r1", "InProgress")
        ok, msg = check_gate("feat-a", "lulu-spec", "feature", tmp_path)
        assert ok is False
        assert "lulu-bet" in msg
        assert "STOP" in msg
        assert "Gate blocked:" not in msg

    def test_reentry_always_allowed(self, tmp_path):
        """Re-entering the current stage is always allowed (no session required)."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "lulu-spec")
        ok, msg = check_gate("feat-a", "lulu-spec", "feature", tmp_path)
        assert ok is True

    def test_stage_not_in_cycle_always_allowed(self, tmp_path):
        """'decision' is not in the feature cycle stages → gate always OK."""
        from start_gate import check_gate
        ok, msg = check_gate("feat-a", "decision", "feature", tmp_path)
        assert ok is True

    def test_topic_cycle_valid_advance(self, tmp_path):
        """Topic cycle: current=lulu-bet (Delivered) → lulu-blueprint allowed."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "topic-a", "lulu-bet")
        _make_workflow_state(tmp_path, "topic-a", "lulu-bet", "r1", "Delivered")
        ok, msg = check_gate("topic-a", "lulu-blueprint", "topic", tmp_path)
        assert ok is True

    def test_stale_cycle_state_treated_as_null(self, tmp_path):
        """cycle-state.json with a stage not in the cycle → treated as NULL."""
        from start_gate import check_gate
        _make_cycle_state(tmp_path, "feat-a", "some-unknown-stage")
        ok, msg = check_gate("feat-a", "lulu-bet", "feature", tmp_path)
        assert ok is True  # NULL → first stage allowed

    def test_full_feature_cycle_sequence(self, tmp_path):
        """Walk through all feature cycle stages in order; each advance requires Delivered."""
        from start_gate import check_gate
        stages = ["lulu-bet", "lulu-spec", "lulu-approach",
                  "lulu-plan", "lulu-tasks", "lulu-code"]
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
        sessions = get_sessions("feat-a", "lulu-plan", tmp_path)
        assert sessions == []

    def test_old_state_names_skipped_for_plan_stage(self, tmp_path):
        from workflow_sessions import get_sessions
        # InProgress is not in _VALID_STATES for plan stages → skipped
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "InProgress")
        sessions = get_sessions("feat-a", "lulu-plan", tmp_path)
        assert sessions == []

    def test_returns_session_info_objects(self, tmp_path):
        from workflow_sessions import SessionInfo, get_sessions
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        sessions = get_sessions("feat-a", "lulu-plan", tmp_path)
        assert len(sessions) == 1
        assert isinstance(sessions[0], SessionInfo)
        assert sessions[0].state == "Delivered"
        assert sessions[0].revision == "revision1"

    def test_flat_stage_inprogress_returned(self, tmp_path):
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "lulu-bet", "r1", "InProgress")
        sessions = get_sessions("feat-a", "lulu-bet", tmp_path)
        assert len(sessions) == 1
        assert sessions[0].state == "InProgress"
        assert sessions[0].revision == "r0"

    def test_flat_stage_delivered_returned(self, tmp_path):
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "lulu-bet", "r1", "Delivered")
        sessions = get_sessions("feat-a", "lulu-bet", tmp_path)
        assert len(sessions) == 1
        assert sessions[0].state == "Delivered"

    def test_session_has_state_path(self, tmp_path):
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Delivered")
        sessions = get_sessions("feat-a", "lulu-plan", tmp_path)
        assert sessions[0].state_path is not None
        assert sessions[0].state_path.exists()

    def test_multiple_revisions_returned(self, tmp_path):
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Delivered",
                             "2026-06-01T10:00:00+00:00")
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r2", "Working",
                             "2026-06-02T10:00:00+00:00")
        sessions = get_sessions("feat-a", "lulu-plan", tmp_path)
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
        self._write_features_json(tmp_path, "feat-a", {"name": "x"})
        result = get_topic_doc("feat-a", "lulu-plan", tmp_path)
        assert result is None

    def test_invalid_topic_id_raises_value_error(self, tmp_path):
        from start_gate import get_topic_doc
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x",
                                   "topic_id": "topic-20260101000000-deadbeef"})
        # cycles.json does not exist → ValueError
        with pytest.raises(ValueError):
            get_topic_doc("feat-a", "lulu-plan", tmp_path)

    def test_tech_code_unmapped_returns_none(self, tmp_path):
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x",
                                   "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t"})
        # lulu-code not in topic_doc_stage
        result = get_topic_doc("feat-a", "lulu-code", tmp_path)
        assert result is None

    def test_valid_topic_no_delivered_session_returns_none(self, tmp_path):
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x",
                                   "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t"})
        # No session files → None
        result = get_topic_doc("feat-a", "lulu-plan", tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# invalidate_downstream
# ---------------------------------------------------------------------------

class TestInvalidateDownstream:
    def test_reopen_product_spec_invalidates_downstream(self, tmp_path):
        """Re-opening lulu-spec: all downstream stages become Invalidated."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "lulu-spec", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "lulu-approach", "r1", "InProgress")
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "lulu-tasks", "r1", "Working")

        invalidate_downstream("feat-a", "lulu-spec", "feature", tmp_path)

        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "lulu-approach", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "lulu-plan", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "lulu-tasks", tmp_path))

    def test_backfill_product_diagnostic_invalidates_product_spec_and_later(self, tmp_path):
        """Back-fill: re-open lulu-bet → lulu-spec and all later stages Invalidated."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "lulu-spec", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "lulu-approach", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "Delivered")

        invalidate_downstream("feat-a", "lulu-bet", "feature", tmp_path)

        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "lulu-spec", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "lulu-approach", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("feat-a", "lulu-plan", tmp_path))

    def test_from_stage_itself_not_modified(self, tmp_path):
        """from_stage sessions are NOT touched by invalidate_downstream."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "lulu-spec", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "lulu-approach", "r1", "InProgress")

        invalidate_downstream("feat-a", "lulu-spec", "feature", tmp_path)

        product_spec = get_sessions("feat-a", "lulu-spec", tmp_path)
        assert len(product_spec) == 1
        assert product_spec[0].state == "Delivered"

    def test_already_invalidated_stays_invalidated_idempotent(self, tmp_path):
        """Idempotent: already-Invalidated session stays Invalidated, no error on repeat call."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "lulu-spec", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "lulu-approach", "r1", "Invalidated")

        invalidate_downstream("feat-a", "lulu-spec", "feature", tmp_path)
        invalidate_downstream("feat-a", "lulu-spec", "feature", tmp_path)

        tech_diag = get_sessions("feat-a", "lulu-approach", tmp_path)
        assert all(s.state == "Invalidated" for s in tech_diag)

    def test_old_state_names_not_modified(self, tmp_path):
        """Sessions with old state names (InProgress in a plan-stage file) are skipped — unchanged."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import stage_subdir
        # Create lulu-plan session with "InProgress" (not in _VALID_STATES for plan stages)
        session_dir = tmp_path / "feat-a" / stage_subdir("lulu-plan") / "revision1"
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "workflow-state.md"
        ws.write_text("---\ncurrent_state: InProgress\n---\n", encoding="utf-8")

        invalidate_downstream("feat-a", "lulu-spec", "feature", tmp_path)

        assert "InProgress" in ws.read_text()


# ---------------------------------------------------------------------------
# Cross-container isolation
# ---------------------------------------------------------------------------

class TestCrossContainerIsolation:
    def test_topic_reopen_does_not_affect_feature_container(self, tmp_path):
        """Re-opening a topic container leaves feature container sessions untouched."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "topic-a", "lulu-bet", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "lulu-blueprint", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "lulu-spec", "r1", "Delivered")
        _make_workflow_state(tmp_path, "feat-a", "lulu-approach", "r1", "Delivered")

        invalidate_downstream("topic-a", "lulu-bet", "topic", tmp_path)

        feat_spec = get_sessions("feat-a", "lulu-spec", tmp_path)
        feat_diag = get_sessions("feat-a", "lulu-approach", tmp_path)
        assert all(s.state == "Delivered" for s in feat_spec)
        assert all(s.state == "Delivered" for s in feat_diag)

    def test_topic_reopen_product_diagnostic_invalidates_all_later(self, tmp_path):
        """Topic re-open lulu-bet → lulu-blueprint, lulu-approach, lulu-arch Invalidated."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "topic-a", "lulu-blueprint", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "lulu-approach", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "lulu-arch", "r1", "Delivered")

        invalidate_downstream("topic-a", "lulu-bet", "topic", tmp_path)

        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "lulu-blueprint", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "lulu-approach", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "lulu-arch", tmp_path))

    def test_topic_reopen_product_arch_invalidates_tech(self, tmp_path):
        """Topic re-open lulu-blueprint → lulu-approach, lulu-arch Invalidated; lulu-blueprint unchanged."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "topic-a", "lulu-blueprint", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "lulu-approach", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "lulu-arch", "r1", "Delivered")

        invalidate_downstream("topic-a", "lulu-blueprint", "topic", tmp_path)

        product_arch = get_sessions("topic-a", "lulu-blueprint", tmp_path)
        assert all(s.state == "Delivered" for s in product_arch)
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "lulu-approach", tmp_path))
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "lulu-arch", tmp_path))

    def test_topic_reopen_tech_diagnostic_invalidates_tech_arch(self, tmp_path):
        """Topic re-open lulu-approach → lulu-arch Invalidated."""
        from invalidation_hook import invalidate_downstream
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "topic-a", "lulu-approach", "r1", "Delivered")
        _make_workflow_state(tmp_path, "topic-a", "lulu-arch", "r1", "Delivered")

        invalidate_downstream("topic-a", "lulu-approach", "topic", tmp_path)

        tech_diag = get_sessions("topic-a", "lulu-approach", tmp_path)
        assert all(s.state == "Delivered" for s in tech_diag)
        assert all(s.state == "Invalidated" for s in get_sessions("topic-a", "lulu-arch", tmp_path))


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

    def _make_delivered_ref(self, cache_dir: Path, cycle_id: str, stage: str) -> Path:
        """Write an entry for ``stage`` into {cycle_id}/delivered-refs.json and return its file path."""
        refs_path = cache_dir / cycle_id / "delivered-refs.json"
        data = json.loads(refs_path.read_text()) if refs_path.exists() else {"version": 1, "entries": {}}
        doc_dir = cache_dir / cycle_id / stage / "revision1"
        doc_dir.mkdir(parents=True, exist_ok=True)
        doc_path = doc_dir / f"{stage}-doc.md"
        doc_path.write_text("# doc\n", encoding="utf-8")
        data.setdefault("entries", {})[stage] = {
            "delivered_type": stage,
            "path": str(doc_path.resolve()),
            "revision": 1,
            "profile_id": stage,
            "delivered_at": "2026-06-01T00:00:00+00:00",
            "source_workflow_state": "",
        }
        refs_path.parent.mkdir(parents=True, exist_ok=True)
        refs_path.write_text(json.dumps(data), encoding="utf-8")
        return doc_path

    def test_tech_design_maps_to_tech_arch_stage(self, tmp_path):
        """feature.lulu-design: topic_doc_stage maps to lulu-arch → get_topic_doc returns path."""
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t"})
        doc_path = self._make_delivered_ref(tmp_path, topic_id, "lulu-arch")

        result = get_topic_doc("feat-a", "lulu-design", tmp_path)

        assert result == doc_path

    def test_tech_plan_unmapped_returns_none(self, tmp_path):
        """feature.lulu-plan: not in topic_doc_stage → returns None."""
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t"})
        self._make_delivered_ref(tmp_path, topic_id, "lulu-arch")

        result = get_topic_doc("feat-a", "lulu-plan", tmp_path)

        assert result is None

    def test_tech_code_unmapped_returns_none_extended(self, tmp_path):
        """feature.lulu-code: not in topic_doc_stage → returns None (no error)."""
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t"})

        result = get_topic_doc("feat-a", "lulu-code", tmp_path)

        assert result is None

    def test_product_spec_maps_to_product_arch(self, tmp_path):
        """feature.lulu-spec: topic_doc_stage maps to lulu-blueprint → returns delivered path."""
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t"})
        doc_path = self._make_delivered_ref(tmp_path, topic_id, "lulu-blueprint")

        result = get_topic_doc("feat-a", "lulu-spec", tmp_path)

        assert result == doc_path

    def test_valid_topic_no_delivered_session_returns_none_extended(self, tmp_path):
        """topic_id valid + no delivered-refs entry for ref stage → returns None."""
        from start_gate import get_topic_doc
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t"})

        result = get_topic_doc("feat-a", "lulu-plan", tmp_path)

        assert result is None

    def test_topic_id_empty_field_returns_none(self, tmp_path):
        """topic_id field present but empty string → returns None, no error."""
        from start_gate import get_topic_doc
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "topic_id": ""})

        result = get_topic_doc("feat-a", "lulu-plan", tmp_path)

        assert result is None

    def test_topic_id_points_to_nonexistent_topic_raises_value_error(self, tmp_path):
        """topic_id not in cycles.json → ValueError raised."""
        from start_gate import get_topic_doc
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x",
                                   "topic_id": "topic-does-not-exist"})
        self._write_topics_json(tmp_path, "topic-other", {"name": "t"})

        with pytest.raises(ValueError):
            get_topic_doc("feat-a", "lulu-plan", tmp_path)

    def test_get_topic_ref_returns_type_and_path(self, tmp_path):
        """get_topic_ref returns {type, path} — type is the topic's ref stage name."""
        from start_gate import get_topic_ref
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t"})
        doc_path = self._make_delivered_ref(tmp_path, topic_id, "lulu-arch")

        result = get_topic_ref("feat-a", "lulu-design", tmp_path)

        assert result == {"type": "lulu-arch", "path": str(doc_path.resolve())}

    def test_get_topic_ref_deleted_doc_file_returns_none(self, tmp_path):
        """delivered-refs entry exists but its file was removed → returns None (no stale path)."""
        from start_gate import get_topic_ref
        topic_id = "topic-20260101000000-aabbccdd"
        self._write_features_json(tmp_path, "feat-a",
                                  {"name": "x", "topic_id": topic_id})
        self._write_topics_json(tmp_path, topic_id, {"name": "t"})
        doc_path = self._make_delivered_ref(tmp_path, topic_id, "lulu-arch")
        doc_path.unlink()

        result = get_topic_ref("feat-a", "lulu-design", tmp_path)

        assert result is None


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_feature_without_topic_id_loads_normally(self, tmp_path):
        """Old cycles.json entry without topic_id field → loads, treated as no topic."""
        from start_gate import get_topic_doc
        fj = tmp_path / "cycles.json"
        fj.write_text(json.dumps({"feat-old": {"name": "legacy"}}),
                      encoding="utf-8")

        result = get_topic_doc("feat-old", "lulu-plan", tmp_path)

        assert result is None

    def test_session_in_progress_state_skipped_no_error(self, tmp_path):
        """Session file with state 'InProgress' in a plan stage → get_sessions silently skips it."""
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "InProgress")

        sessions = get_sessions("feat-a", "lulu-plan", tmp_path)

        assert sessions == []

    def test_session_ready_for_delivery_state_skipped_no_error(self, tmp_path):
        """Session file with state 'ReadyForDelivery' → get_sessions silently skips it."""
        from workflow_sessions import get_sessions
        _make_workflow_state(tmp_path, "feat-a", "lulu-plan", "r1", "ReadyForDelivery")

        sessions = get_sessions("feat-a", "lulu-plan", tmp_path)

        assert sessions == []
