"""Tests for invalidation_hook.py: flat rewrite and invalidate_downstream."""

import json
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from invalidation_hook import (
    COMPOSE_STAGES,
    _invalidate_flat_session,
    invalidate_downstream,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(tmp_path: Path, container: str, stage: str, revision: str,
                current_state: str, extra_fields: Optional[Dict] = None) -> Path:
    from workflow_sessions import STAGE_FLAT, stage_subdir
    if stage in STAGE_FLAT:
        state_dir = tmp_path / container / stage_subdir(stage)
        state_dir.mkdir(parents=True, exist_ok=True)
        state_path = state_dir / "session-state.md"
    else:
        rev_dir = tmp_path / container / stage_subdir(stage) / revision
        rev_dir.mkdir(parents=True, exist_ok=True)
        state_path = rev_dir / "workflow-state.md"
    fields = {
        "version": "1",
        "workflow": stage,
        "current_state": current_state,
        "updated_at": "2026-06-01T00:00:00Z",
    }
    if extra_fields:
        fields.update(extra_fields)
    lines = ["---"] + [f"{k}: {v}" for k, v in fields.items()] + ["---\n"]
    state_path.write_text("\n".join(lines), encoding="utf-8")
    return state_path


def _write_compose_session_v2(
    cache_dir: Path,
    cycle_id: str,
    stage: str,
    *,
    active_doc: int = 1,
    version: int = 2,
) -> Path:
    session_dir = cache_dir / cycle_id / stage
    session_dir.mkdir(parents=True, exist_ok=True)
    ss = session_dir / "session-state.md"
    ss.write_text(
        "---\n"
        f"version: {version}\n"
        f"active_doc: {active_doc}\n"
        "profile_path: /tmp/compose-profile.json\n"
        f"profile_digest: {'a' * 64}\n"
        "start_id: test-start\n"
        "holder_finalized: true\n"
        "updated_at: 2026-06-01T00:00:00Z\n"
        "---\n",
        encoding="utf-8",
    )
    return ss


def _write_compose_workflow(
    cache_dir: Path,
    cycle_id: str,
    stage: str,
    *,
    active_doc: int = 1,
    current_state: str = "Delivered",
) -> Path:
    rev = cache_dir / cycle_id / stage / f"revision{active_doc}"
    rev.mkdir(parents=True, exist_ok=True)
    ws = rev / "workflow-state.md"
    ws.write_text(
        "---\n"
        "version: 1\n"
        "workflow: tech-doc\n"
        "mode: tech\n"
        "cycle_type: feature\n"
        f"current_state: {current_state}\n"
        "evaluate_round: 0\n"
        "updated_at: 2026-06-01T00:00:00Z\n"
        "---\n",
        encoding="utf-8",
    )
    return ws


def _make_tt_config(config_dir: Path,
                    feature_stages: List[str],
                    topic_stages: List[str]) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)

    def _chain(stages: List[str]) -> List[dict]:
        entries: List[dict] = [{"from": None, "to": [stages[0]]}]
        for i in range(len(stages) - 1):
            entries.append({"from": stages[i], "to": [stages[i + 1]]})
        entries.append({"from": stages[-1], "to": []})
        return entries

    tt = {
        "version": 2,
        "topic_doc_stage": {s: s for s in topic_stages},
        "topic": _chain(topic_stages),
        "feature": _chain(feature_stages),
    }
    (config_dir / "transition-table.json").write_text(json.dumps(tt), encoding="utf-8")


FEATURE_STAGES = [
    "lulu-bet", "lulu-spec",
    "lulu-approach", "lulu-plan",
    "lulu-tasks", "lulu-exec",
]
TOPIC_STAGES = [
    "lulu-bet", "lulu-blueprint",
    "lulu-approach", "lulu-arch",
]


# ---------------------------------------------------------------------------
# _invalidate_flat_session
# ---------------------------------------------------------------------------

class TestWriteInvalidated:
    def test_changes_current_state_to_invalidated(self, tmp_path):
        sp = _make_state(tmp_path, "c", "lulu-approach", "r1", "Delivered")
        _invalidate_flat_session(sp)
        from workflow_sessions import parse_frontmatter
        assert parse_frontmatter(sp.read_text())["current_state"] == "Invalidated"

    def test_preserves_other_frontmatter_fields(self, tmp_path):
        sp = _make_state(tmp_path, "c", "lulu-approach", "r1", "Drafting",
                         extra_fields={"evaluate_round": "2", "tech_ref": "/a/b.md",
                                       "updated_at": "2026-05-01T12:00:00Z"})
        _invalidate_flat_session(sp)
        from workflow_sessions import parse_frontmatter
        fm = parse_frontmatter(sp.read_text())
        assert fm["current_state"] == "Invalidated"
        assert fm["version"] == "1"
        assert fm["workflow"] == "lulu-approach"
        assert fm["evaluate_round"] == "2"
        assert fm["tech_ref"] == "/a/b.md"
        assert fm["updated_at"] == "2026-05-01T12:00:00Z"

    def test_already_invalidated_stays_invalidated(self, tmp_path):
        sp = _make_state(tmp_path, "c", "lulu-approach", "r1", "Invalidated")
        _invalidate_flat_session(sp)
        from workflow_sessions import parse_frontmatter
        assert parse_frontmatter(sp.read_text())["current_state"] == "Invalidated"

    def test_written_file_has_valid_frontmatter_block(self, tmp_path):
        sp = _make_state(tmp_path, "c", "lulu-approach", "r1", "Evaluating")
        _invalidate_flat_session(sp)
        content = sp.read_text()
        assert content.startswith("---\n")
        assert "---" in content[3:]


# ---------------------------------------------------------------------------
# invalidate_downstream
# ---------------------------------------------------------------------------

class TestInvalidateDownstream:
    @pytest.fixture(autouse=True)
    def patch_config(self, tmp_path, monkeypatch):
        import start_gate
        import transition_table

        config_dir = tmp_path / "config"
        _make_tt_config(config_dir, FEATURE_STAGES, TOPIC_STAGES)
        monkeypatch.setattr(start_gate, "_CONFIG_DIR", config_dir)
        monkeypatch.setattr(
            transition_table,
            "_CONFIG_PATH",
            config_dir / "transition-table.json",
        )
        self.cache_dir = tmp_path

    def test_feature_reopen_product_spec_invalidates_downstream(self):
        from_sp = _make_state(self.cache_dir, "feat-1", "lulu-spec", "r1", "Drafting")
        _make_state(self.cache_dir, "feat-1", "lulu-approach", "r1", "Delivered")
        _write_compose_session_v2(self.cache_dir, "feat-1", "lulu-plan")
        plan_ws = _write_compose_workflow(self.cache_dir, "feat-1", "lulu-plan")
        for stage in ["lulu-tasks", "lulu-exec"]:
            _make_state(self.cache_dir, "feat-1", stage, "r1", "Delivered")

        invalidate_downstream("feat-1", "lulu-spec", "feature", self.cache_dir)

        from workflow_sessions import parse_frontmatter, stage_subdir
        assert parse_frontmatter(from_sp.read_text())["current_state"] == "Drafting"
        approach = self.cache_dir / "feat-1" / stage_subdir("lulu-approach") / "session-state.md"
        assert parse_frontmatter(approach.read_text())["current_state"] == "Invalidated"
        assert parse_frontmatter(plan_ws.read_text())["current_state"] == "Invalidated"
        for stage in ["lulu-tasks", "lulu-exec"]:
            sp = self.cache_dir / "feat-1" / stage_subdir(stage) / "r1" / "workflow-state.md"
            assert parse_frontmatter(sp.read_text())["current_state"] == "Invalidated", stage

    def test_topic_reopen_product_diagnostic_invalidates_downstream(self):
        from_sp = _make_state(self.cache_dir, "topic-1", "lulu-bet", "r1", "Drafting")
        _make_state(self.cache_dir, "topic-1", "lulu-approach", "r1", "Delivered")
        _write_compose_session_v2(self.cache_dir, "topic-1", "lulu-blueprint")
        blueprint_ws = _write_compose_workflow(
            self.cache_dir, "topic-1", "lulu-blueprint", current_state="Delivered"
        )
        _write_compose_session_v2(self.cache_dir, "topic-1", "lulu-arch")
        arch_ws = _write_compose_workflow(
            self.cache_dir, "topic-1", "lulu-arch", current_state="Delivered"
        )

        invalidate_downstream("topic-1", "lulu-bet", "topic", self.cache_dir)

        from workflow_sessions import parse_frontmatter, stage_subdir
        assert parse_frontmatter(from_sp.read_text())["current_state"] == "Drafting"
        approach = self.cache_dir / "topic-1" / stage_subdir("lulu-approach") / "session-state.md"
        assert parse_frontmatter(approach.read_text())["current_state"] == "Invalidated"
        assert parse_frontmatter(blueprint_ws.read_text())["current_state"] == "Invalidated"
        assert parse_frontmatter(arch_ws.read_text())["current_state"] == "Invalidated"

    def test_compose_v1_session_skipped_with_warning(self):
        _write_compose_session_v2(self.cache_dir, "feat-1", "lulu-plan", version=1)
        ws = _write_compose_workflow(self.cache_dir, "feat-1", "lulu-plan")
        with pytest.warns(UserWarning, match="invalidation skip"):
            invalidate_downstream("feat-1", "lulu-spec", "feature", self.cache_dir)
        from workflow_sessions import parse_frontmatter
        assert parse_frontmatter(ws.read_text())["current_state"] == "Delivered"

    def test_compose_invalidates_only_active_revision(self):
        _write_compose_session_v2(self.cache_dir, "feat-1", "lulu-plan", active_doc=2)
        old_ws = _write_compose_workflow(
            self.cache_dir, "feat-1", "lulu-plan", active_doc=1, current_state="Delivered"
        )
        active_ws = _write_compose_workflow(
            self.cache_dir, "feat-1", "lulu-plan", active_doc=2, current_state="Working"
        )
        invalidate_downstream("feat-1", "lulu-spec", "feature", self.cache_dir)
        from workflow_sessions import parse_frontmatter
        assert parse_frontmatter(old_ws.read_text())["current_state"] == "Delivered"
        assert parse_frontmatter(active_ws.read_text())["current_state"] == "Invalidated"

    def test_only_writes_current_state_other_fields_preserved(self):
        _make_state(self.cache_dir, "feat-1", "lulu-approach", "r1", "Delivered",
                    extra_fields={"evaluate_round": "3", "tech_ref": "/ref.md"})
        invalidate_downstream("feat-1", "lulu-spec", "feature", self.cache_dir)
        from workflow_sessions import parse_frontmatter, stage_subdir
        sp = self.cache_dir / "feat-1" / stage_subdir("lulu-approach") / "session-state.md"
        fm = parse_frontmatter(sp.read_text())
        assert fm["current_state"] == "Invalidated"
        assert fm["evaluate_round"] == "3"
        assert fm["tech_ref"] == "/ref.md"

    def test_does_not_modify_from_stage(self):
        _write_compose_session_v2(self.cache_dir, "feat-1", "lulu-plan")
        from_sp = _write_compose_workflow(
            self.cache_dir, "feat-1", "lulu-plan", current_state="Working"
        )
        _make_state(self.cache_dir, "feat-1", "lulu-tasks", "r1", "Delivered")
        invalidate_downstream("feat-1", "lulu-plan", "feature", self.cache_dir)
        from workflow_sessions import parse_frontmatter
        assert parse_frontmatter(from_sp.read_text())["current_state"] == "Working"

    def test_downstream_stage_no_sessions_no_error(self):
        invalidate_downstream("feat-1", "lulu-spec", "feature", self.cache_dir)

    def test_already_invalidated_stays_invalidated(self):
        _write_compose_session_v2(self.cache_dir, "feat-1", "lulu-plan")
        sp = _write_compose_workflow(
            self.cache_dir, "feat-1", "lulu-plan", current_state="Invalidated"
        )
        invalidate_downstream("feat-1", "lulu-spec", "feature", self.cache_dir)
        from workflow_sessions import parse_frontmatter
        assert parse_frontmatter(sp.read_text())["current_state"] == "Invalidated"

    def test_idempotent_second_call(self):
        _write_compose_session_v2(self.cache_dir, "feat-1", "lulu-plan")
        _write_compose_workflow(self.cache_dir, "feat-1", "lulu-plan")
        invalidate_downstream("feat-1", "lulu-spec", "feature", self.cache_dir)
        invalidate_downstream("feat-1", "lulu-spec", "feature", self.cache_dir)
        from workflow_sessions import parse_frontmatter
        sp = self.cache_dir / "feat-1" / "lulu-plan" / "revision1" / "workflow-state.md"
        assert parse_frontmatter(sp.read_text())["current_state"] == "Invalidated"

    def test_only_affects_given_cycle_id(self):
        _write_compose_session_v2(self.cache_dir, "feat-1", "lulu-plan")
        _write_compose_workflow(self.cache_dir, "feat-1", "lulu-plan")
        _write_compose_session_v2(self.cache_dir, "feat-2", "lulu-plan")
        sp2 = _write_compose_workflow(self.cache_dir, "feat-2", "lulu-plan")
        invalidate_downstream("feat-1", "lulu-spec", "feature", self.cache_dir)
        from workflow_sessions import parse_frontmatter
        assert parse_frontmatter(sp2.read_text())["current_state"] == "Delivered"

    def test_old_named_sessions_not_modified(self):
        """Non-active revision dirs are not rewritten by compose invalidation."""
        from workflow_sessions import stage_subdir
        rev_dir = self.cache_dir / "feat-1" / stage_subdir("lulu-plan") / "r1"
        rev_dir.mkdir(parents=True, exist_ok=True)
        sp = rev_dir / "workflow-state.md"
        sp.write_text(
            "---\nversion: 1\nworkflow: lulu-plan\ncurrent_state: InProgress\n"
            "updated_at: 2026-01-01T00:00:00Z\n---\n",
            encoding="utf-8",
        )
        invalidate_downstream("feat-1", "lulu-spec", "feature", self.cache_dir)
        content = sp.read_text()
        assert "InProgress" in content
        assert "Invalidated" not in content

    def test_compose_stages_constant(self):
        assert COMPOSE_STAGES == {
            "lulu-arch",
            "lulu-blueprint",
            "lulu-design",
            "lulu-plan",
            "lulu-spec",
        }
